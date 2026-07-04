import {
    isPermissionGranted,
    requestPermission,
    sendNotification,
} from "@tauri-apps/plugin-notification";
import { LazyStore } from "@tauri-apps/plugin-store";
import { getRuns, getRunDetail } from "./client";
import { getNotificationsEnabled } from "./settings";
import type { RunChangeDto, RunSummaryDto } from "./types";

const store = new LazyStore("settings.json");
const POLL_INTERVAL_MS = 90_000;

let pollHandle: ReturnType<typeof setInterval> | null = null;
let permissionGranted = false;

async function ensurePermission(): Promise<boolean> {
    if (permissionGranted) return true;
    try {
        permissionGranted = await isPermissionGranted();
        if (!permissionGranted) {
            permissionGranted = (await requestPermission()) === "granted";
        }
    } catch (err) {
        console.error("[notifications] permission check failed:", err);
        return false;
    }
    return permissionGranted;
}

// Pure — no I/O. `runs` must be newest-first (what getRuns() already returns).
// Returns the runs to notify for, oldest-first, so toasts land in order.
export function selectNewRuns(
    runs: RunSummaryDto[],
    lastNotifiedRunId: string | null,
): RunSummaryDto[] {
    if (runs.length === 0) return [];
    if (lastNotifiedRunId === null) return [runs[0]]; // first poll ever — only the latest, not all history
    return runs.filter((r) => r.runId > lastNotifiedRunId).reverse(); // ISO-8601 sorts lexically
}

// Pure — no I/O.
export function formatChange(c: RunChangeDto): string {
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

export async function pollOnce() {
    const notificationsEnabled = await getNotificationsEnabled();

    // Skip the OS permission dance entirely when notifications are off — no
    // reason to prompt for something that won't fire.
    if (notificationsEnabled) {
        if (!(await ensurePermission())) return;
    }

    const lastNotifiedRunId =
        (await store.get<string>("lastNotifiedRunId")) ?? null;

    let runs: RunSummaryDto[];
    try {
        runs = await getRuns();
    } catch {
        return;
    }
    if (runs.length === 0) return;

    const newRuns = selectNewRuns(runs, lastNotifiedRunId);

    if (notificationsEnabled) {
        for (const run of newRuns) {
            try {
                const detail = await getRunDetail(run.runId);
                notifyForChanges(detail.changes);
            } catch {
                // a malformed or since-rotated log file — skip it, don't block later runs
            }
        }
    }
    // When disabled, detection/dedup bookkeeping still runs below — only the
    // toast is skipped. lastNotifiedRunId still has to advance even on this
    // branch, or re-enabling later replays everything missed as one burst.

    if (newRuns.length > 0) {
        await store.set("lastNotifiedRunId", runs[0].runId);
        await store.save();
    }
}

export function startNotificationPolling() {
    if (pollHandle) return;
    pollOnce().catch((err) => console.error("[notifications] pollOnce failed:", err));
    pollHandle = setInterval(() => {
        pollOnce().catch((err) => console.error("[notifications] pollOnce failed:", err));
    }, POLL_INTERVAL_MS);
}

export function stopNotificationPolling() {
    if (pollHandle) clearInterval(pollHandle);
    pollHandle = null;
}
