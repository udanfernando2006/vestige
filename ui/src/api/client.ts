import { getApiBaseUrl } from "./settings";
import type {
    BookGroupDto,
    BookCreateDto,
    BookDto,
    StoreDto,
    StoreCreateDto,
    TrackingPairDto,
    TrackingPairCreateDto,
    TrackingPairUpdateDto,
    AvailabilityDto,
    SnapshotHistoryDto,
    RunSummaryDto,
    DiscoverResultDto,
} from "./types";

export class ApiError extends Error {
    status: number;
    body: unknown;
    constructor(message: string, status: number, body: unknown) {
        super(message);
        this.status = status;
        this.body = body;
    }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const baseUrl = await getApiBaseUrl();
    const res = await fetch(`${baseUrl}${path}`, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(options.headers ?? {}),
        },
    });

    if (res.status === 204) return undefined as T;

    const text = await res.text();
    const data = text ? JSON.parse(text) : undefined;

    if (!res.ok) {
        // GlobalExceptionHandler returns { error: "..." } for 404/409/500;
        // RunController's local handlers return { error, output } for 422/500.
        const message =
            data && typeof data === "object" && "error" in data
                ? String((data as { error: unknown }).error)
                : `Request failed with status ${res.status}`;
        throw new ApiError(message, res.status, data);
    }

    return data as T;
}

// ---- Health ----

export function checkHealth(): Promise<{ status: string }> {
    return request("/actuator/health");
}

// ---- Books ----

export function getBooks(): Promise<BookGroupDto[]> {
    return request("/api/books");
}

export function createBook(dto: BookCreateDto): Promise<BookDto> {
    return request("/api/books", { method: "POST", body: JSON.stringify(dto) });
}

export function deleteBook(id: number): Promise<void> {
    return request(`/api/books/${id}`, { method: "DELETE" });
}

// ---- Stores ----

export function getStores(): Promise<StoreDto[]> {
    return request("/api/stores");
}

export function createStore(dto: StoreCreateDto): Promise<StoreDto> {
    return request("/api/stores", {
        method: "POST",
        body: JSON.stringify(dto),
    });
}

// ---- Tracking ----

export function getTracking(): Promise<TrackingPairDto[]> {
    return request("/api/tracking");
}

export function getNeedsSetup(): Promise<TrackingPairDto[]> {
    return request("/api/tracking/needs-setup");
}

export function createTracking(
    dto: TrackingPairCreateDto,
): Promise<TrackingPairDto> {
    return request("/api/tracking", {
        method: "POST",
        body: JSON.stringify(dto),
    });
}

export function updateTracking(
    id: number,
    dto: Partial<TrackingPairUpdateDto>,
): Promise<TrackingPairDto> {
    return request(`/api/tracking/${id}`, {
        method: "PATCH",
        body: JSON.stringify(dto),
    });
}

// ---- Availability ----

export function getAvailability(): Promise<AvailabilityDto[]> {
    return request("/api/availability");
}

export function getHistory(
    isbn: string,
    limit = 50,
): Promise<SnapshotHistoryDto[]> {
    return request(`/api/availability/history/${isbn}?limit=${limit}`);
}

// ---- Runs ----

export function getRuns(): Promise<RunSummaryDto[]> {
    return request("/api/runs");
}

export function triggerRun(): Promise<RunSummaryDto> {
    return request("/api/runs/trigger", { method: "POST" });
}

export function discoverSelectors(pairId: number): Promise<DiscoverResultDto> {
    return request(`/api/runs/discover/${pairId}`, { method: "POST" });
}
