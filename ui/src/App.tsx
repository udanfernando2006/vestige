import { useEffect, useState, useCallback, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import Dashboard from "./pages/Dashboard";
import Books from "./pages/Books";
import Stores from "./pages/Stores";
import Tracking from "./pages/Tracking";
import History from "./pages/History";
import Settings from "./pages/Settings";
import { checkHealth } from "./api/client";
import {
    startNotificationPolling,
    stopNotificationPolling,
} from "./api/notifications";
import { getAutoDockerEnabled, isLocalDeployment } from "./api/settings";

type Page =
    | "dashboard"
    | "books"
    | "stores"
    | "tracking"
    | "history"
    | "settings";

const NAV: { id: Page; label: string }[] = [
    { id: "dashboard", label: "Dashboard" },
    { id: "books", label: "Books" },
    { id: "stores", label: "Stores" },
    { id: "tracking", label: "Tracking" },
    { id: "history", label: "History" },
    { id: "settings", label: "Settings" },
];

type DockerStatus = "idle" | "checking" | "starting" | "unavailable" | "ready";

export default function App() {
    const [page, setPage] = useState<Page>("dashboard");
    const [backendStatus, setBackendStatus] = useState<
        "checking" | "ready" | "unreachable"
    >("checking");
    const [dockerStatus, setDockerStatus] = useState<DockerStatus>("idle");
    const [dockerLog, setDockerLog] = useState<string[]>([]);
    const dockerFlowStarted = useRef(false);

    const probe = useCallback(async () => {
        setBackendStatus("checking");
        for (let attempt = 0; attempt < 10; attempt++) {
            try {
                await checkHealth();
                setBackendStatus("ready");
                return;
            } catch {
                await new Promise((r) => setTimeout(r, 1500));
            }
        }
        setBackendStatus("unreachable");
    }, []);

    const appendLog = useCallback((line: string) => {
        console.log("[vestige]", line);
        setDockerLog((prev) => [...prev, line]);
    }, []);

    const startDockerFlow = useCallback(async () => {
        if (dockerFlowStarted.current) return;
        dockerFlowStarted.current = true;

        const local = await isLocalDeployment();
        const autoEnabled = await getAutoDockerEnabled();
        if (!local || !autoEnabled) {
            probe();
            return;
        }

        setDockerStatus("checking");
        appendLog("Checking for Docker...");
        const available = await invoke<boolean>("check_docker_available");
        if (!available) {
            setDockerStatus("unavailable");
            appendLog("Docker is not installed or not running.");
            return;
        }
        appendLog("Docker found.");

        setDockerStatus("starting");
        appendLog("Starting Vestige containers...");
        try {
            await invoke("start_docker_stack");
            const unconfigured = await invoke<boolean>(
                "is_env_unconfigured",
            ).catch(() => false);
            if (unconfigured) {
                appendLog(
                    "Using default local configuration (edit .env in the Vestige app-data folder to customize).",
                );
            }
            appendLog("Containers started. Waiting for the API...");
            setDockerStatus("ready");
            probe();
        } catch (err) {
            setDockerStatus("unavailable");
            appendLog(`Failed to start containers: ${err}`);
        }
    }, [probe, appendLog]);

    useEffect(() => {
        startDockerFlow();
    }, [startDockerFlow]);

    useEffect(() => {
        startNotificationPolling();
        return () => stopNotificationPolling();
    }, []);

    useEffect(() => {
        const unlisten = listen("quit-requested", async () => {
            const local = await isLocalDeployment();
            const autoEnabled = await getAutoDockerEnabled();
            if (local && autoEnabled) {
                await invoke("stop_docker_stack").catch(() => {
                    // Best-effort — a failed stop must never block quitting.
                });
            }
            await invoke("confirm_quit");
        });
        return () => {
            unlisten.then((f) => f());
        };
    }, []);

    if (dockerStatus === "checking" || dockerStatus === "starting") {
        return (
            <div className="app-shell">
                <div className="backend-gate-wrap">
                    <div className="vestige-window backend-gate">
                        <div className="vestige-titlebar">
                            <span>Vestige — Starting Local Backend</span>
                        </div>
                        <div className="vestige-window-body backend-gate-body">
                            <pre className="docker-terminal">
                                {dockerLog.join("\n")}
                            </pre>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    if (dockerStatus === "unavailable" && page !== "settings") {
        return (
            <div className="app-shell">
                <div className="backend-gate-wrap">
                    <div className="vestige-window backend-gate">
                        <div className="vestige-titlebar">
                            <span>Vestige</span>
                        </div>
                        <div className="vestige-window-body backend-gate-body">
                            <p>
                                Docker isn't available on this machine, so
                                Vestige can't start its local backend
                                automatically. Install Docker Desktop and make
                                sure it's running, or start the backend manually
                                and disable auto-start in Settings.
                            </p>
                            <button onClick={startDockerFlow}>Retry</button>
                            <button
                                className="vestige-btn-danger"
                                onClick={() => setPage("settings")}>
                                Open Settings
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    // Settings must always be reachable, even before the backend is up or if the
    // configured URL is wrong — otherwise there's no way to fix it from the UI.
    if (backendStatus !== "ready" && page !== "settings") {
        return (
            <div className="app-shell">
                <div className="backend-gate-wrap">
                    <div className="vestige-window backend-gate">
                        <div className="vestige-titlebar">
                            <span>Vestige</span>
                        </div>
                        <div className="vestige-window-body backend-gate-body">
                            {backendStatus === "checking" && (
                                <p>Connecting to the API…</p>
                            )}
                            {backendStatus === "unreachable" && (
                                <>
                                    <p>
                                        Couldn't reach the Spring Boot API. Make
                                        sure <code>docker-compose up</code> (or
                                        the API jar) is running.
                                    </p>
                                    <button onClick={probe}>Retry</button>
                                </>
                            )}
                            <button
                                className="vestige-btn-danger"
                                onClick={() => setPage("settings")}>
                                Open Settings
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="app-shell">
            <aside className="vestige-window vestige-sidebar">
                <div className="vestige-titlebar">
                    <span>Vestige</span>
                </div>
                <nav className="vestige-sidebar-nav">
                    {NAV.map((n) => (
                        <button
                            key={n.id}
                            className={`vestige-nav-btn ${
                                n.id === page ? "vestige-nav-active" : ""
                            }`.trim()}
                            onClick={() => setPage(n.id)}>
                            {n.label}
                        </button>
                    ))}
                </nav>
            </aside>
            <main className="main-content">
                {page === "dashboard" && <Dashboard />}
                {page === "books" && <Books />}
                {page === "stores" && <Stores />}
                {page === "tracking" && <Tracking />}
                {page === "history" && <History />}
                {page === "settings" && <Settings />}
            </main>
        </div>
    );
}
