import { describe, it, expect } from "vitest";
import { selectNewRuns, formatChange } from "./notifications";
import type { RunChangeDto, RunSummaryDto } from "./types";

const run = (runId: string): RunSummaryDto => ({
    runId,
    totalPairs: 1,
    changes: 0,
    errors: 0,
    durationSeconds: 1,
    logPath: "",
});

describe("selectNewRuns", () => {
    it("returns nothing when there are no runs", () => {
        expect(selectNewRuns([], null)).toEqual([]);
    });

    it("on the first poll ever, returns only the latest run", () => {
        const runs = [run("2026-06-20T08:00:00Z"), run("2026-06-19T08:00:00Z")];
        expect(selectNewRuns(runs, null)).toEqual([
            run("2026-06-20T08:00:00Z"),
        ]);
    });

    it("returns runs strictly newer than the last notified one, oldest-first", () => {
        const runs = [
            run("2026-06-20T08:00:00Z"),
            run("2026-06-19T08:00:00Z"),
            run("2026-06-18T08:00:00Z"),
        ];
        const result = selectNewRuns(runs, "2026-06-18T08:00:00Z");
        expect(result.map((r) => r.runId)).toEqual([
            "2026-06-19T08:00:00Z",
            "2026-06-20T08:00:00Z",
        ]);
    });

    it("returns nothing when no run is newer than the last notified one", () => {
        expect(
            selectNewRuns(
                [run("2026-06-20T08:00:00Z")],
                "2026-06-20T08:00:00Z",
            ),
        ).toEqual([]);
    });
});

describe("formatChange", () => {
    const base: RunChangeDto = {
        pairId: 1,
        bookName: "The Last Wish",
        storeName: "sarasavi",
        fromStatus: "IN_STOCK",
        toStatus: "IN_STOCK",
    };

    it("formats a status-only change", () => {
        expect(formatChange({ ...base, toStatus: "OUT_OF_STOCK" })).toBe(
            "The Last Wish @ sarasavi: IN_STOCK → OUT_OF_STOCK",
        );
    });

    it("formats a price-only change", () => {
        expect(formatChange({ ...base, fromPrice: 1500, toPrice: 1400 })).toBe(
            "The Last Wish @ sarasavi: price 1500.00 → 1400.00",
        );
    });

    it("formats a combined status + price change", () => {
        expect(
            formatChange({
                ...base,
                toStatus: "OUT_OF_STOCK",
                fromPrice: 1500,
                toPrice: 1450,
            }),
        ).toBe(
            "The Last Wish @ sarasavi: IN_STOCK → OUT_OF_STOCK, 1500.00 → 1450.00",
        );
    });

    it("falls back to status-only when toPrice is missing, not undefined.toFixed()", () => {
        // OUT_OF_STOCK scrapes often come back with no price found this run —
        // this is the case that would crash on a naive implementation.
        expect(
            formatChange({
                ...base,
                toStatus: "OUT_OF_STOCK",
                fromPrice: 1500,
                toPrice: undefined,
            }),
        ).toBe("The Last Wish @ sarasavi: IN_STOCK → OUT_OF_STOCK");
    });
});
