import { useEffect, useState, useCallback } from "react";
import { getStores, createStore } from "../api/client";
import type { StoreDto } from "../api/types";

export default function Stores() {
    const [stores, setStores] = useState<StoreDto[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [name, setName] = useState("");
    const [baseUrl, setBaseUrl] = useState("");
    const [submitting, setSubmitting] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            setStores(await getStores());
        } catch (err) {
            setError(
                err instanceof Error ? err.message : "Failed to load stores",
            );
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    async function handleAdd(e: React.FormEvent) {
        e.preventDefault();
        setSubmitting(true);
        setError(null);
        try {
            await createStore({ name, baseUrl });
            setName("");
            setBaseUrl("");
            await load();
        } catch (err) {
            setError(
                err instanceof Error ? err.message : "Failed to add store",
            );
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <div className="page">
            <h2>Stores</h2>
            {error && <p className="form-error">{error}</p>}

            <form className="card" onSubmit={handleAdd}>
                <h3>Add store</h3>
                <label>
                    Name{" "}
                    <input
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        required
                    />
                </label>
                <label>
                    Base URL
                    <input
                        value={baseUrl}
                        onChange={(e) => setBaseUrl(e.target.value)}
                        placeholder="https://…"
                        required
                    />
                </label>
                <button type="submit" disabled={submitting}>
                    {submitting ? "Adding…" : "Add store"}
                </button>
            </form>

            <div className="card">
                <table>
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Base URL</th>
                        </tr>
                    </thead>
                    <tbody>
                        {loading ? (
                            <tr>
                                <td colSpan={2}>Loading…</td>
                            </tr>
                        ) : (
                            stores.map((s) => (
                                <tr key={s.id}>
                                    <td>{s.name}</td>
                                    <td>{s.baseUrl}</td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
                <p className="muted">
                    There's no delete action here yet — the API layer doesn't
                    expose <code>DELETE /api/stores/{"{id}"}</code> (see Part
                    18).
                </p>
            </div>
        </div>
    );
}
