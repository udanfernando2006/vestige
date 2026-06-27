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

// Whether notifications.ts's poller should actually fire an OS notification
// when it finds a run with changes. Local, device-level — unlike the LLM/
// scheduler fields on the same page, this never touches Spring Boot or
// scraper-server, since detection happens server-side either way and firing
// is the one part of this feature that lives entirely in this layer
// (vestige_guide_v3.md Section 11). Defaults to true so existing installs
// behave exactly as before this toggle existed.
let cachedNotificationsEnabled: boolean | null = null;

export async function getNotificationsEnabled(): Promise<boolean> {
    if (cachedNotificationsEnabled !== null) return cachedNotificationsEnabled;
    const stored = await store.get<boolean>("notificationsEnabled");
    cachedNotificationsEnabled = stored ?? true;
    return cachedNotificationsEnabled;
}

export async function setNotificationsEnabled(enabled: boolean): Promise<void> {
    await store.set("notificationsEnabled", enabled);
    await store.save();
    cachedNotificationsEnabled = enabled; // applied immediately, same as setApiBaseUrl
}

