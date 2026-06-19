import { useEffect, useState, useCallback } from "react";
import { getBooks, createBook, deleteBook } from "../api/client";
import type { BookGroupDto } from "../api/types";

export default function Books() {
    const [groups, setGroups] = useState<BookGroupDto[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [name, setName] = useState("");
    const [isbn, setIsbn] = useState("");
    const [seriesName, setSeriesName] = useState("");
    const [isSeriesEntry, setIsSeriesEntry] = useState(false);
    const [submitting, setSubmitting] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            setGroups(await getBooks());
        } catch (err) {
            setError(
                err instanceof Error ? err.message : "Failed to load books",
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
            await createBook({
                name,
                isbn,
                isSeriesEntry,
                seriesName: seriesName || null,
            });
            setName("");
            setIsbn("");
            setSeriesName("");
            setIsSeriesEntry(false);
            await load();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to add book");
        } finally {
            setSubmitting(false);
        }
    }

    async function handleDelete(id: number, title: string) {
        const confirmed = window.confirm(
            `Delete "${title}"? This also deletes all tracking pairs and history for this book.`,
        );
        if (!confirmed) return;
        try {
            await deleteBook(id);
            await load();
        } catch (err) {
            setError(
                err instanceof Error ? err.message : "Failed to delete book",
            );
        }
    }

    return (
        <div className="page">
            <h2>Books</h2>
            {error && <p className="form-error">{error}</p>}

            <form className="card" onSubmit={handleAdd}>
                <h3>Add book</h3>
                <label>
                    Name{" "}
                    <input
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        required
                    />
                </label>
                <label>
                    ISBN{" "}
                    <input
                        value={isbn}
                        onChange={(e) => setIsbn(e.target.value)}
                        required
                    />
                </label>
                <label>
                    Series (optional){" "}
                    <input
                        value={seriesName}
                        onChange={(e) => setSeriesName(e.target.value)}
                    />
                </label>
                <label className="checkbox-label">
                    <input
                        type="checkbox"
                        checked={isSeriesEntry}
                        onChange={(e) => setIsSeriesEntry(e.target.checked)}
                    />
                    Part of a series
                </label>
                <button type="submit" disabled={submitting}>
                    {submitting ? "Adding…" : "Add book"}
                </button>
            </form>

            {loading ? (
                <p>Loading…</p>
            ) : (
                groups.map((g) => (
                    <div
                        key={g.seriesName ?? "__standalone__"}
                        className="card">
                        <h3>{g.seriesName ?? "Standalone"}</h3>
                        <table>
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>ISBN</th>
                                    <th></th>
                                </tr>
                            </thead>
                            <tbody>
                                {g.books.map((b) => (
                                    <tr key={b.id}>
                                        <td>{b.name}</td>
                                        <td>{b.isbn}</td>
                                        <td>
                                            <button
                                                className="link-button"
                                                onClick={() =>
                                                    handleDelete(b.id, b.name)
                                                }>
                                                Delete
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ))
            )}
        </div>
    );
}
