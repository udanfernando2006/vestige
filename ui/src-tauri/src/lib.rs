use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager,
};

use tauri_plugin_shell::ShellExt;
use tauri::Emitter;
use std::fs;
use std::path::PathBuf;
use std::time::Duration;
use tokio::sync::oneshot;
use std::sync::Mutex;
use base64::{engine::general_purpose::URL_SAFE, Engine as _};
use rand::RngCore;

// Holds the pending "quit confirmed" signal between the tray menu event
// (which fires the "quit-requested" event to JS) and the JS response
// (which invokes confirm_quit below). None when no quit is in flight.
struct QuitState(Mutex<Option<oneshot::Sender<bool>>>);

/// Called by App.tsx once it has freshly computed whether to stop the Docker
/// stack (autoDockerEnabled && isLocalDeployment, evaluated live at quit time,
/// never cached) and has actually done so (or decided not to). Signals the
/// waiting quit handler to proceed with app.exit(0).
#[tauri::command]
fn confirm_quit(state: tauri::State<QuitState>) {
    if let Some(tx) = state.0.lock().unwrap().take() {
        let _ = tx.send(true);
    }
}

/// Generates a fresh 32-byte key, urlsafe-base64 encoded — matches
/// SettingsCipher.__init__'s exact requirement in security/crypto.py
/// (decodes to exactly 32 bytes for AES-256). Called once per install,
/// never reused across machines, unlike the old static template value.
fn generate_encryption_key() -> String {
    let mut key = [0u8; 32];
    rand::thread_rng().fill_bytes(&mut key);
    URL_SAFE.encode(key)
}

const ENV_TEMPLATE_MARKER: &str = "VESTIGE_TEMPLATE_MARKER=unconfigured";

/// Returns the app-data-relative Vestige project directory: <app_data_dir>/Vestige/
/// Confirmed convention: "Vestige" (productName), not the reverse-DNS identifier.
fn vestige_dir(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    use tauri::Manager as _;
    let base = app
        .path()
        .app_data_dir()
        .map_err(|e| e.to_string())?;
    Ok(base) // Tauri's app_data_dir() already resolves to .../Vestige/ given productName "Vestige"
}

/// Copies bundled resources into the writable app-data directory on first run only.
/// Never overwrites an existing .env — that would clobber a user's real credentials.
fn seed_project_files(app: &tauri::AppHandle) -> Result<(), String> {
    use tauri::Manager as _;
    let dir = vestige_dir(app)?;
    eprintln!("[vestige] project dir: {}", dir.display());
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    fs::create_dir_all(dir.join("logs")).map_err(|e| e.to_string())?;

    let resource_dir = app
        .path()
        .resource_dir()
        .map_err(|e| e.to_string())?
        .join("resources");

    let compose_dest = dir.join("docker-compose.yml");
    if !compose_dest.exists() {
        fs::copy(resource_dir.join("docker-compose.yml"), &compose_dest)
            .map_err(|e| e.to_string())?;
    }

    let env_dest = dir.join(".env");
    if !env_dest.exists() {
        let template = fs::read_to_string(resource_dir.join(".env.template"))
            .map_err(|e| e.to_string())?;
        let key = generate_encryption_key();
        let populated: String = template
            .lines()
            .map(|line| {
                if line.trim_start().starts_with("SETTINGS_ENCRYPTION_KEY=") {
                    format!("SETTINGS_ENCRYPTION_KEY={key}")
                } else {
                    line.to_string()
                }
            })
            .collect::<Vec<_>>()
            .join("\n");
        fs::write(&env_dest, populated).map_err(|e| e.to_string())?;
     }

    let books_dest = dir.join("books_config.json");
    if !books_dest.exists() {
        fs::copy(resource_dir.join("books_config.json"), &books_dest)
            .map_err(|e| e.to_string())?;
    }

    Ok(())
}

/// Sentinel check: true if the live .env still contains the "unconfigured" marker.
#[tauri::command]
fn is_env_unconfigured(app: tauri::AppHandle) -> Result<bool, String> {
    let dir = vestige_dir(&app)?;
    let env_path = dir.join(".env");
    let contents = fs::read_to_string(&env_path).map_err(|e| e.to_string())?;
    Ok(contents.contains(ENV_TEMPLATE_MARKER))
}

/// `docker info` — checks both "is docker installed" and "is the engine running"
/// in one call, since a missing binary and a stopped engine both fail this the
/// same way (non-zero exit), which is sufficient for the UI's purposes: either
/// way, the answer is "can't proceed automatically."
#[tauri::command]
async fn check_docker_available(app: tauri::AppHandle) -> Result<bool, String> {
    let shell = app.shell();
    match shell.command("docker").args(["info"]).output().await {
        Ok(output) => {
            eprintln!("[vestige] docker info exit status: {:?}", output.status);
            Ok(output.status.success())
        }
        Err(e) => {
            eprintln!("[vestige] docker info failed to launch: {e}");
            Ok(false)
        }
    }
}

#[tauri::command]
async fn start_docker_stack(app: tauri::AppHandle) -> Result<(), String> {
    seed_project_files(&app)?;
    let dir = vestige_dir(&app)?;
    let compose_path = dir.join("docker-compose.yml");
    let shell = app.shell();
    let output = shell
        .command("docker")
        .args([
            "compose",
            "-f",
            compose_path.to_str().ok_or("invalid path")?,
            "up",
            "-d",
        ])
        .output()
        .await
        .map_err(|e| e.to_string())?;
    if output.status.success() {
        Ok(())
    } else {
        Err(String::from_utf8_lossy(&output.stderr).to_string())
    }
}

#[tauri::command]
async fn stop_docker_stack(app: tauri::AppHandle) -> Result<(), String> {
    let dir = vestige_dir(&app)?;
    let compose_path = dir.join("docker-compose.yml");
    if !compose_path.exists() {
        return Ok(()); // never seeded / never started — nothing to stop
    }
    let shell = app.shell();
    let output = shell
        .command("docker")
        .args([
            "compose",
            "-f",
            compose_path.to_str().ok_or("invalid path")?,
            "down",
        ])
        .output()
        .await
        .map_err(|e| e.to_string())?;
    if output.status.success() {
        Ok(())
    } else {
        Err(String::from_utf8_lossy(&output.stderr).to_string())
    }
}


#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_store::Builder::default().build())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_shell::init())
        .manage(QuitState(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![
            is_env_unconfigured,
            check_docker_available,
            start_docker_stack,
            stop_docker_stack,
            confirm_quit
        ])
        .setup(|app| {
            let show_i = MenuItem::with_id(app, "show", "Show Vestige", true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_i, &quit_i])?;

            TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    "quit" => {
                        let app_handle = app.clone();
                        tauri::async_runtime::spawn(async move {
                            // JS owns the decision (autoDockerEnabled  isLocalDeployment,
                            // both computed live, never cached) and calls stop_docker_stack
                            // itself if warranted, then invokes confirm_quit. This handler
                            // just waits for that signal, with a timeout fallback so a
                            // frozen/unresponsive webview can never hang Quit.
                            let (tx, rx) = oneshot::channel::<bool>();
                            {
                                let state = app_handle.state::<QuitState>();
                                *state.0.lock().unwrap() = Some(tx);
                            }
                            let _ = app_handle.emit("quit-requested", ());

                            // NOTE: 5s is a judgment call, not a spec value — adjust if
                            // `docker compose down` realistically takes longer on your
                            // machine under load.
                            let _ = tokio::time::timeout(Duration::from_secs(5), rx).await;
                            app_handle.exit(0);
                        });
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                })
                .build(app)?;

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                window.hide().unwrap();
                api.prevent_close();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}