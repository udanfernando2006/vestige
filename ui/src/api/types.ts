export type PairStatus =
    | "PENDING"
    | "NEEDS_SETUP"
    | "IN_STOCK"
    | "OUT_OF_STOCK"
    | "NOT_LISTED"
    | "SKIP"
    | "ERROR";

// ---- Books ----

export interface BookDto {
    id: number;
    name: string;
    isbn: string;
    isSeriesEntry: boolean;
    seriesId?: number;
    seriesName?: string;
}

export interface BookGroupDto {
    seriesName?: string; // absent for the standalone-books group
    books: BookDto[];
}

export interface BookCreateDto {
    name: string;
    isbn: string;
    isSeriesEntry: boolean;
    seriesName?: string | null;
}

// ---- Stores ----

export interface StoreDto {
    id: number;
    name: string;
    baseUrl: string;
}

export interface StoreCreateDto {
    name: string;
    baseUrl: string;
}

// ---- Tracking ----

export interface TrackingBookSummary {
    id: number;
    name: string;
    isbn: string;
}

export interface TrackingStoreSummary {
    id: number;
    name: string;
}

export interface TrackingPairDto {
    id: number;
    book: TrackingBookSummary;
    store: TrackingStoreSummary;
    productUrl?: string;
    selectorsCached: boolean;
    status: PairStatus;
    lastScrapedAt?: string; // ISO-8601
}

export interface TrackingPairCreateDto {
    isbn: string;
    storeName: string;
    productUrl?: string | null;
}

export interface TrackingPairUpdateDto {
    productUrl?: string | null;
    priceSelector?: string | null;
    stockSelector?: string | null;
    status?: PairStatus | null;
}

// ---- Availability ----

export interface AvailabilityDto {
    pairId: number;
    bookName: string;
    storeName: string;
    status: PairStatus;
    price?: number;
    productUrl?: string;
    scrapedAt: string;
}

export interface SnapshotHistoryDto {
    storeName: string;
    status: PairStatus;
    price?: number;
    scrapedAt: string;
}

// ---- Runs ----

export interface RunSummaryDto {
    runId: string;
    totalPairs: number;
    changes: number;
    errors: number;
    durationSeconds: number;
    logPath?: string; // only populated by GET /api/runs
}

export interface DiscoverResultDto {
    pairId: number;
    priceSelector?: string;
    stockSelector?: string;
    priceSample?: string;
    stockSample?: string;
    modelUsed?: string;
    reason?: string; // populated only on failure
    committed: boolean;
}

// ---- Settings ----
export interface SettingsDto {
    llmDiscoveryEnabled: boolean;
    llmMode: string;
    selectorApiBase: string;
    selectorApiKeyConfigured: boolean;
    selectorApiKeyHint?: string;
    selectorModel: string;
    directApiBase: string;
    directApiKeyConfigured: boolean;
    directApiKeyHint?: string;
    directModel: string;
}

export interface SettingsUpdateDto {
    llmDiscoveryEnabled?: boolean;
    llmMode?: string;
    selectorApiBase?: string;
    selectorApiKey?: string;
    selectorModel?: string;
    directApiBase?: string;
    directApiKey?: string;
    directModel?: string;
}
