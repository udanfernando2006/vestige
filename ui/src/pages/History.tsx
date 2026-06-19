import { useEffect, useState, useCallback, useMemo } from "react";
import { getBooks, getHistory } from "../api/client";
import type { BookGroupDto, SnapshotHistoryDto } from "../api/types";
import AvailabilityBadge from "../components/AvailabilityBadge";

export default function History() {
    const [bookGroups, setBookGroups] = useState<BookGroupDto[]>([]);
    const [isbn, setIsbn] = useState("");
    const [snapshots, setSnapshots] = useState<SnapshotHistoryDto[]>([]);
    const [storeFilter, setStoreFilter] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        getBooks()
            .then(setBookGroups)
            .catch((err) => setError(err.message));
    }, []);

    const loadHistory = useCallback(async (selectedIsbn: string) => {
        if (!selectedIsbn) {
            setSnapshots([]);
            return;
        }
        setLoading(true);
        setError(null);
        try {
            setSnapshots(await getHistory(selectedIsbn, 100));
        } catch (err) {
            setError(
                err instanceof Error ? err.message : "Failed to load history",
            );
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadHistory(isbn);
    }, [isbn, loadHistory]);

    const storeNames = useMemo(
        () => [...new Set(snapshots.map((s) => s.storeName))],
        [snapshots],
    );
    const filtered = storeFilter
        ? snapshots.filter((s) => s.storeName === storeFilter)
        : snapshots;
    const books = bookGroups.flatMap((g) => g.books);

    return (
        <div className="page">
            <h2>History</h2>
            {error && <p className="form-error">{error}</p>}

            <div className="card">
                <label>
                    Book
                    <select
                        value={isbn}
                        onChange={(e) => {
                            setIsbn(e.target.value);
                            setStoreFilter("");
                        }}>
                        <option value="">Select a book…</option>
                        {books.map((b) => (
                            <option key={b.isbn} value={b.isbn}>
                                {b.name}
                            </option>
                        ))}
                    </select>
                </label>
                {storeNames.length > 1 && (
                    <label>
                        Store
                        <select
                            value={storeFilter}
                            onChange={(e) => setStoreFilter(e.target.value)}>
                            <option value="">All stores</option>
                            {storeNames.map((s) => (
                                <option key={s} value={s}>
                                    {s}
                                </option>
                            ))}
                        </select>
                    </label>
                )}
            </div>

            <div className="card">
                {loading ? (
                    <p>Loading…</p>
                ) : (
                    <table>
                        <thead>
                            <tr>
                                <th>Store</th>
                                <th>Status</th>
                                <th>Price</th>
                                <th>Scraped at</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.map((s, i) => (
                                <tr key={`${s.storeName}-${s.scrapedAt}-${i}`}>
                                    <td>{s.storeName}</td>
                                    <td>
                                        <AvailabilityBadge status={s.status} />
                                    </td>
                                    <td>
                                        {s.price != null
                                            ? s.price.toFixed(2)
                                            : "—"}
                                    </td>
                                    <td>
                                        {new Date(s.scrapedAt).toLocaleString()}
                                    </td>
                                </tr>
                            ))}
                            {filtered.length === 0 && isbn && (
                                <tr>
                                    <td colSpan={4} className="muted">
                                        No history yet for this book.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
}
