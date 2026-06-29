import { useEffect, useState, useCallback } from "react";
import Dashboard from "./pages/Dashboard";
import Books from "./pages/Books";
import Stores from "./pages/Stores";
import Tracking from "./pages/Tracking";
import History from "./pages/History";
import Settings from "./pages/Settings";
import { checkHealth } from "./api/client";
import { startNotificationPolling, stopNotificationPolling } from "./api/notifications";

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

export default function App() {
    const [page, setPage] = useState<Page>("dashboard");
    const [backendStatus, setBackendStatus] = useState<
        "checking" | "ready" | "unreachable"
    >("checking");

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

    useEffect(() => {
        probe();
    }, [probe]);

    useEffect(() => {
        startNotificationPolling();
        return () => stopNotificationPolling();
    }, []);

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
                                        Couldn't reach the Spring Boot API.
                                        Make sure{" "}
                                        <code>docker-compose up</code> (or the
                                        API jar) is running.
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
