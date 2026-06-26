import {
    isPermissionGranted,
    requestPermission,
    sendNotification,
} from "@tauri-apps/plugin-notification";
import { LazyStore } from "@tauri-apps/plugin-store";
import { getRuns, getRunDetail } from "./client";
import type { RunChangeDto } from "./types";

const store = new LazyStore("settings.json");
const POLL_INTERVAL_MS = 90_000; // slower than the scheduler's 60s tick — no reason to poll faster than a run can complete

let pollHandle: ReturnType<typeof setInterval> | null = null;
let permissionGranted = false;

async function ensurePermission(): Promise<boolean> {
    if (permissionGranted) return true;
    permissionGranted = await isPermissionGranted();
    if (!permissionGranted) {
        permissionGranted = (await requestPermission()) === "granted";
    }
    return permissionGranted;
}

function formatChange(c: RunChangeDto): string {
    const statusChanged = !!c.fromStatus && c.fromStatus !== c.toStatus;
    const priceChanged =
        c.fromPrice != null && c.toPrice != null && c.fromPrice !== c.toPrice;

    if (statusChanged && priceChanged) {
        return `${c.bookName} @ ${c.storeName}: ${c.fromStatus} → ${c.toStatus}, ${c.fromPrice!.toFixed(2)} → ${c.toPrice!.toFixed(2)}`;
    }
    if (statusChanged) {
        return `${c.bookName} @ ${c.storeName}: ${c.fromStatus} → ${c.toStatus}`;
    }
    return `${c.bookName} @ ${c.storeName}: price ${c.fromPrice!.toFixed(2)} → ${c.toPrice!.toFixed(2)}`;
}

function notifyForChanges(changes: RunChangeDto[]) {
    if (changes.length === 0) return;
    const lines = changes.slice(0, 3).map(formatChange);
    const more = changes.length > 3 ? `\n+${changes.length - 3} more` : "";

    sendNotification({
        title:
            changes.length === 1
                ? "Availability changed"
                : `${changes.length} books changed`,
        body: lines.join("\n") + more,
    });
}

async function pollOnce() {
    if (!(await ensurePermission())) return;

    const lastNotifiedRunId =
        (await store.get<string>("lastNotifiedRunId")) ?? null;

    let runs;
    try {
        runs = await getRuns(); // newest-first, per RunService.getRecentRuns()
    } catch {
        return; // backend unreachable this tick — try again next poll
    }
    if (runs.length === 0) return;

    // First time ever: only the latest run, not the entire history.
    // Otherwise: every run strictly newer than the last one we've notified for.
    const newRuns = lastNotifiedRunId
        ? runs.filter((r) => r.runId > lastNotifiedRunId) // ISO-8601 strings sort correctly lexically
        : [runs[0]];

    for (const run of newRuns.reverse()) {
        // oldest-first, so toasts appear in chronological order
        try {
            const detail = await getRunDetail(run.runId);
            notifyForChanges(detail.changes);
        } catch {
            // a malformed or since-rotated log file — skip it, don't block later runs
        }
    }

    await store.set("lastNotifiedRunId", runs[0].runId);
    await store.save();
}

export function startNotificationPolling() {
    if (pollHandle) return; // idempotent — guards against React StrictMode's double-mount in dev
    pollOnce();
    pollHandle = setInterval(pollOnce, POLL_INTERVAL_MS);
}

export function stopNotificationPolling() {
    if (pollHandle) clearInterval(pollHandle);
    pollHandle = null;
}
