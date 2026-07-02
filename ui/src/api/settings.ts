import { LazyStore } from "@tauri-apps/plugin-store";

export const DEFAULT_API_BASE_URL = "http://localhost:8080";

const store = new LazyStore("settings.json");

let cachedBaseUrl: string | null = null;

export async function getApiBaseUrl(): Promise<string> {
    if (cachedBaseUrl) return cachedBaseUrl;
    const stored = await store.get<string>("apiBaseUrl");
    cachedBaseUrl = stored ?? DEFAULT_API_BASE_URL;
    return cachedBaseUrl;
}

export async function setApiBaseUrl(url: string): Promise<void> {
    // Strip a trailing slash so client.ts never builds a `//api/...` URL
    const trimmed = url.trim().replace(/\/+$/, "");
    await store.set("apiBaseUrl", trimmed);
    await store.save();
    cachedBaseUrl = trimmed; // applied immediately — no restart needed
}

// Whether notifications.ts's poller should actually fire an OS notification
// when it finds a run with changes. Local, device-level — unlike the LLM/
// scheduler fields on the same page, this never touches Spring Boot or
// scraper-server, since detection happens server-side either way and firing
// is the one part of this feature that lives entirely in this layer
// (vestige_guide_v3.md Section 11). Defaults to true so existing installs
// behave exactly as before this toggle existed.
let cachedNotificationsEnabled: boolean | null = null;

export async function getNotificationsEnabled(): Promise<boolean> {
    if (cachedNotificationsEnabled !== null) return cachedNotificationsEnabled;
    const stored = await store.get<boolean>("notificationsEnabled");
    cachedNotificationsEnabled = stored ?? true;
    return cachedNotificationsEnabled;
}

export async function setNotificationsEnabled(enabled: boolean): Promise<void> {
    await store.set("notificationsEnabled", enabled);
    await store.save();
    cachedNotificationsEnabled = enabled; // applied immediately, same as setApiBaseUrl
}

// Whether the app should automatically start the local Docker stack on launch
// and stop it (docker compose down only — never the Docker engine itself,
// confirmed) on quit. Only ever consulted when the configured API base URL
// resolves to localhost/127.0.0.1 — see App.tsx's gating logic. Defaults to
// true so a fresh local install "just works" without a manual toggle visit.
let cachedAutoDockerEnabled: boolean | null = null;

export async function getAutoDockerEnabled(): Promise<boolean> {
    if (cachedAutoDockerEnabled !== null) return cachedAutoDockerEnabled;
    const stored = await store.get<boolean>("autoDockerEnabled");
    cachedAutoDockerEnabled = stored ?? true;
    return cachedAutoDockerEnabled;
}

export async function setAutoDockerEnabled(enabled: boolean): Promise<void> {
    await store.set("autoDockerEnabled", enabled);
    await store.save();
    cachedAutoDockerEnabled = enabled;
}

/** Returns true only if the configured API base URL points at this machine. */
export async function isLocalDeployment(): Promise<boolean> {
    const url = await getApiBaseUrl();
    try {
        const hostname = new URL(url).hostname;
        return hostname === "localhost" || hostname === "127.0.0.1";
    } catch {
        return false;
    }
}
