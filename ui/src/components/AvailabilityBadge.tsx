import type { PairStatus } from "../api/types";

const LABELS: Record<PairStatus, string> = {
    PENDING: "Pending",
    NEEDS_SETUP: "Needs setup",
    IN_STOCK: "In stock",
    OUT_OF_STOCK: "Out of stock",
    NOT_LISTED: "Not listed",
    SKIP: "Skipped",
    ERROR: "Error",
};

export default function AvailabilityBadge({ status }: { status: string }) {
    const key = (status in LABELS ? status : "ERROR") as PairStatus;
    const cssClass = `badge badge-${key.toLowerCase().replace(/_/g, "-")}`;
    return <span className={cssClass}>{LABELS[key]}</span>;
}
