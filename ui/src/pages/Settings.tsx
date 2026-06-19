import { useEffect, useState } from "react";
import {
    getApiBaseUrl,
    setApiBaseUrl,
    DEFAULT_API_BASE_URL,
} from "../api/settings";
import { checkHealth } from "../api/client";

export default function Settings() {
    const [url, setUrl] = useState(DEFAULT_API_BASE_URL);
    const [saved, setSaved] = useState(false);
    const [testResult, setTestResult] = useState<"idle" | "ok" | "fail">(
        "idle",
    );
    const [testing, setTesting] = useState(false);

    useEffect(() => {
        getApiBaseUrl().then(setUrl);
    }, []);

    async function handleSave(e: React.FormEvent) {
        e.preventDefault();
        await setApiBaseUrl(url);
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
    }

    async function handleTest() {
        setTesting(true);
        setTestResult("idle");
        try {
            await checkHealth();
            setTestResult("ok");
        } catch {
            setTestResult("fail");
        } finally {
            setTesting(false);
        }
    }

    return (
        <div className="page">
            <h2>Settings</h2>
            <form className="card" onSubmit={handleSave}>
                <label>
                    API base URL
                    <input
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        placeholder="http://localhost:8080"
                    />
                </label>
                <p className="muted">
                    Use <code>http://localhost:8080</code> locally, or the
                    EC2/Azure VM public IP on port 8080 once deployed to the
                    cloud.
                </p>
                <div className="settings-actions">
                    <button type="submit">Save</button>
                    <button
                        type="button"
                        onClick={handleTest}
                        disabled={testing}>
                        {testing ? "Testing…" : "Test connection"}
                    </button>
                </div>
                {saved && (
                    <p className="form-success">Saved — applied immediately.</p>
                )}
                {testResult === "ok" && (
                    <p className="form-success">
                        Connected — backend is reachable.
                    </p>
                )}
                {testResult === "fail" && (
                    <p className="form-error">
                        Could not reach the backend at this URL.
                    </p>
                )}
            </form>
        </div>
    );
}
