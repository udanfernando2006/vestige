import { LazyStore } from "@tauri-apps/plugin-store";

export const DEFAULT_API_BASE_URL = "http://localhost:8080";

const store = new LazyStore("settings.json");

let cachedBaseUrl: string | null = null;

export async function getApiBaseUrl(): Promise<string> {
    if (cachedBaseUrl) return cachedBaseUrl;
    const stored = await store.get<string>("apiBaseUrl");
    cachedBaseUrl = stored ?? DEFAULT_API_BASE_URL;
    return cachedBaseUrl;
}

export async function setApiBaseUrl(url: string): Promise<void> {
    // Strip a trailing slash so client.ts never builds a `//api/...` URL
    const trimmed = url.trim().replace(/\/+$/, "");
    await store.set("apiBaseUrl", trimmed);
    await store.save();
    cachedBaseUrl = trimmed; // applied immediately — no restart needed
}
