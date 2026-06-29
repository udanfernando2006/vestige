import { useEffect, useState } from "react";
import {
    getApiBaseUrl,
    setApiBaseUrl,
    DEFAULT_API_BASE_URL,
    getNotificationsEnabled,
    setNotificationsEnabled,
} from "../api/settings";
import { checkHealth, getSettings, updateSettings } from "../api/client";
import type { SettingsDto, SettingsUpdateDto } from "../api/types";
import Window from "../components/Window";

export default function Settings() {
    const [url, setUrl] = useState(DEFAULT_API_BASE_URL);
    const [saved, setSaved] = useState(false);
    const [testResult, setTestResult] = useState<"idle" | "ok" | "fail">(
        "idle",
    );
    const [testing, setTesting] = useState(false);

    const [notificationsEnabled, setNotificationsEnabledState] = useState(true);
    const [notificationsLoaded, setNotificationsLoaded] = useState(false);

    const [pipeline, setPipeline] = useState<SettingsDto | null>(null);
    const [pipelineError, setPipelineError] = useState<string | null>(null);
    const [syncing, setSyncing] = useState(false);
    const [pipelineSaved, setPipelineSaved] = useState(false);

    const [draft, setDraft] = useState({
        llmDiscoveryEnabled: false,
        llmMode: "direct",
        scrapeIntervalHours: "" as number | "", // '' renders as a blank box, means disabled
        selectorApiBase: "",
        selectorApiKey: "", // secret fields start blank — never pre-filled with the real value
        selectorModel: "",
        directApiBase: "",
        directApiKey: "",
        directModel: "",
    });

    function loadPipelineSettings() {
        setPipelineError(null);
        getSettings()
            .then((s) => {
                setPipeline(s);
                setDraft((d) => ({
                    ...d,
                    llmDiscoveryEnabled: s.llmDiscoveryEnabled,
                    llmMode: s.llmMode,
                    scrapeIntervalHours: s.scrapeIntervalHours ?? "",
                    selectorApiBase: s.selectorApiBase,
                    selectorApiKey: "",
                    selectorModel: s.selectorModel,
                    directApiBase: s.directApiBase,
                    directApiKey: "",
                    directModel: s.directModel,
                }));
            })
            .catch((err) =>
                setPipelineError(
                    err instanceof Error
                        ? err.message
                        : "Failed to load pipeline settings",
                ),
            );
    }

    useEffect(() => {
        getApiBaseUrl().then(setUrl);
        getNotificationsEnabled().then((enabled) => {
            setNotificationsEnabledState(enabled);
            setNotificationsLoaded(true);
        });
        loadPipelineSettings();
    }, []);

    async function handleSaveConnection(e: React.FormEvent) {
        e.preventDefault();
        await setApiBaseUrl(url);
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
        loadPipelineSettings();
    }

    async function handleToggleNotifications(checked: boolean) {
        setNotificationsEnabledState(checked); // optimistic
        await setNotificationsEnabled(checked);
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

    async function handleSavePipeline(e: React.FormEvent) {
        e.preventDefault();
        setSyncing(true);
        setPipelineError(null);
        try {
            const update: SettingsUpdateDto = {
                llmDiscoveryEnabled: draft.llmDiscoveryEnabled,
                llmMode: draft.llmMode,
                // '' means disabled — send 0, which the scraper service converts
                // into an explicit "" clear on the SCRAPE_INTERVAL_HOURS override.
                scrapeIntervalHours:
                    draft.scrapeIntervalHours === ""
                        ? 0
                        : draft.scrapeIntervalHours,
                selectorApiBase: draft.selectorApiBase,
                selectorModel: draft.selectorModel,
                directApiBase: draft.directApiBase,
                directModel: draft.directModel,
                ...(draft.selectorApiKey
                    ? { selectorApiKey: draft.selectorApiKey }
                    : {}),
                ...(draft.directApiKey
                    ? { directApiKey: draft.directApiKey }
                    : {}),
            };
            await updateSettings(update);
            setPipelineSaved(true);
            setTimeout(() => setPipelineSaved(false), 2000);
            loadPipelineSettings();
        } catch (err) {
            setPipelineError(
                err instanceof Error
                    ? err.message
                    : "Failed to save pipeline settings",
            );
        } finally {
            setSyncing(false);
        }
    }

    function clearKey(field: "selectorApiKey" | "directApiKey") {
        updateSettings({ [field]: "" } as SettingsUpdateDto)
            .then(loadPipelineSettings)
            .catch((err) =>
                setPipelineError(
                    err instanceof Error ? err.message : "Failed to clear key",
                ),
            );
    }

    return (
        <div className="page">
            <h2>Settings</h2>

            <Window title="Backend connection">
                <form onSubmit={handleSaveConnection}>
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
                        EC2/Azure VM public IP on port 8080 once deployed to
                        the cloud.
                    </p>
                    {/* <div className="flex gap-2"> */}
                    <div className="btn-group">
                        <button type="submit">Save</button>
                        <button
                            type="button"
                            className="vestige-btn-secondary"
                            onClick={handleTest}
                            disabled={testing}>
                            {testing ? "Testing…" : "Test connection"}
                        </button>
                    </div>
                    {saved && (
                        <p className="form-success">
                            Saved — applied immediately.
                        </p>
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
            </Window>

            <Window title="Notifications">
                <label className="checkbox-label">
                    <input
                        type="checkbox"
                        checked={notificationsEnabled}
                        disabled={!notificationsLoaded}
                        onChange={(e) =>
                            handleToggleNotifications(e.target.checked)
                        }
                    />
                    Show a desktop notification when a tracked book's price or
                    stock changes
                </label>
                <p className="muted">
                    Takes effect on the next check, within about 90 seconds —
                    no restart needed. Turning this off doesn't pause checking
                    for changes, so turning it back on later won't replay
                    everything that happened while it was off.
                </p>
            </Window>

            <Window title="Pipeline configuration">
                <form onSubmit={handleSavePipeline}>
                    {pipelineError && (
                        <p className="form-error">{pipelineError}</p>
                    )}
                    {!pipeline ? (
                        <p className="muted">Loading…</p>
                    ) : (
                        <>
                            <label>
                                LLM mode
                                <select
                                    value={draft.llmMode}
                                    onChange={(e) =>
                                        setDraft({
                                            ...draft,
                                            llmMode: e.target.value,
                                        })
                                    }>
                                    <option value="direct">
                                        Direct extraction (Path D)
                                    </option>
                                    <option value="selector">
                                        Selector discovery (Path B/C)
                                    </option>
                                </select>
                            </label>
                            <label className="checkbox-label">
                                <input
                                    type="checkbox"
                                    checked={draft.llmDiscoveryEnabled}
                                    onChange={(e) =>
                                        setDraft({
                                            ...draft,
                                            llmDiscoveryEnabled:
                                                e.target.checked,
                                        })
                                    }
                                />
                                Run selector discovery automatically in the
                                pipeline
                            </label>

                            <h4>Automation</h4>
                            <label>
                                Run scraper automatically every (hours)
                                <input
                                    type="number"
                                    min="1"
                                    step="1"
                                    placeholder="Disabled"
                                    value={draft.scrapeIntervalHours}
                                    onChange={(e) =>
                                        setDraft({
                                            ...draft,
                                            scrapeIntervalHours:
                                                e.target.value === ""
                                                    ? ""
                                                    : Number(e.target.value),
                                        })
                                    }
                                />
                            </label>
                            <p className="muted">
                                Checked roughly once a minute — actual run
                                time may drift slightly from the exact hour
                                mark. Leave blank to disable.
                            </p>

                            <h4>Selector discovery (Path B)</h4>
                            <label>
                                API base
                                <input
                                    value={draft.selectorApiBase}
                                    onChange={(e) =>
                                        setDraft({
                                            ...draft,
                                            selectorApiBase: e.target.value,
                                        })
                                    }
                                />
                            </label>
                            <label>
                                API key{" "}
                                {pipeline.selectorApiKeyConfigured && (
                                    <span className="muted">
                                        currently set (
                                        {pipeline.selectorApiKeyHint})
                                    </span>
                                )}
                                <input
                                    type="password"
                                    value={draft.selectorApiKey}
                                    onChange={(e) =>
                                        setDraft({
                                            ...draft,
                                            selectorApiKey: e.target.value,
                                        })
                                    }
                                    placeholder={
                                        pipeline.selectorApiKeyConfigured
                                            ? "Leave blank to keep current key"
                                            : "Not set"
                                    }
                                />
                                {pipeline.selectorApiKeyConfigured && (
                                    <button
                                        type="button"
                                        className="mt-2"
                                        onClick={() =>
                                            clearKey("selectorApiKey")
                                        }>
                                        Clear key
                                    </button>
                                )}
                            </label>
                            <label>
                                Model
                                <input
                                    value={draft.selectorModel}
                                    onChange={(e) =>
                                        setDraft({
                                            ...draft,
                                            selectorModel: e.target.value,
                                        })
                                    }
                                />
                            </label>

                            <h4>Direct extraction (Path D)</h4>
                            <label>
                                API base
                                <input
                                    value={draft.directApiBase}
                                    onChange={(e) =>
                                        setDraft({
                                            ...draft,
                                            directApiBase: e.target.value,
                                        })
                                    }
                                />
                            </label>
                            <label>
                                API key{" "}
                                {pipeline.directApiKeyConfigured && (
                                    <span className="muted">
                                        currently set (
                                        {pipeline.directApiKeyHint})
                                    </span>
                                )}
                                <input
                                    type="password"
                                    value={draft.directApiKey}
                                    onChange={(e) =>
                                        setDraft({
                                            ...draft,
                                            directApiKey: e.target.value,
                                        })
                                    }
                                    placeholder={
                                        pipeline.directApiKeyConfigured
                                            ? "Leave blank to keep current key"
                                            : "Not set"
                                    }
                                />
                                {pipeline.directApiKeyConfigured && (
                                    <button
                                        type="button"
                                        className="mt-2"
                                        onClick={() =>
                                            clearKey("directApiKey")
                                        }>
                                        Clear key
                                    </button>
                                )}
                            </label>
                            <label>
                                Model
                                <input
                                    value={draft.directModel}
                                    onChange={(e) =>
                                        setDraft({
                                            ...draft,
                                            directModel: e.target.value,
                                        })
                                    }
                                />
                            </label>

                            <button type="submit" disabled={syncing}>
                                {syncing
                                    ? "Saving…"
                                    : "Save pipeline settings"}
                            </button>
                            {pipelineSaved && (
                                <p className="form-success">
                                    Saved — takes effect on the next run, no
                                    restart needed.
                                </p>
                            )}
                        </>
                    )}
                </form>
            </Window>
        </div>
    );
}
