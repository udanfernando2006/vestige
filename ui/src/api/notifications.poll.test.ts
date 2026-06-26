import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@tauri-apps/plugin-notification", () => ({
    isPermissionGranted: vi.fn(),
    requestPermission: vi.fn(),
    sendNotification: vi.fn(),
}));
vi.mock("@tauri-apps/plugin-store", () => ({
    LazyStore: vi.fn().mockImplementation(function () {
        return {
            get: vi.fn(),
            set: vi.fn(),
            save: vi.fn(),
        };
    }),
}));
vi.mock("./client", () => ({ getRuns: vi.fn(), getRunDetail: vi.fn() }));

import {
    isPermissionGranted,
    requestPermission,
    sendNotification,
} from "@tauri-apps/plugin-notification";
import { getRuns, getRunDetail } from "./client";
import { pollOnce } from "./notifications";

describe("pollOnce", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(isPermissionGranted).mockResolvedValue(true);
    });

    it("does nothing if notification permission is denied", async () => {
        vi.mocked(isPermissionGranted).mockResolvedValue(false);
        vi.mocked(requestPermission).mockResolvedValue("denied");

        await pollOnce();

        expect(getRuns).not.toHaveBeenCalled();
    });

    it("fires a notification for the latest run on the first-ever poll", async () => {
        vi.mocked(getRuns).mockResolvedValue([
            {
                runId: "2026-06-20T08:00:00Z",
                totalPairs: 1,
                changes: 1,
                errors: 0,
                durationSeconds: 1,
                logPath: "",
            },
        ]);
        vi.mocked(getRunDetail).mockResolvedValue({
            runId: "2026-06-20T08:00:00Z",
            totalPairs: 1,
            errors: 0,
            durationSeconds: 1,
            changes: [
                {
                    pairId: 1,
                    bookName: "The Last Wish",
                    storeName: "sarasavi",
                    fromStatus: "OUT_OF_STOCK",
                    toStatus: "IN_STOCK",
                },
            ],
        });

        await pollOnce();

        expect(sendNotification).toHaveBeenCalledTimes(1);
    });

    it("skips cleanly without throwing if the backend is unreachable", async () => {
        vi.mocked(getRuns).mockRejectedValue(new Error("network error"));

        await expect(pollOnce()).resolves.not.toThrow();
        expect(sendNotification).not.toHaveBeenCalled();
    });
});
