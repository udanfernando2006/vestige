package io.github.udanfernando.vestige.repository;

import io.github.udanfernando.vestige.entity.AvailabilitySnapshot;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import java.util.List;
import java.util.Optional;

public interface AvailabilitySnapshotRepository extends JpaRepository<AvailabilitySnapshot, Long> {

    @Query("""
        SELECT a FROM AvailabilitySnapshot a
        JOIN FETCH a.pair p
        JOIN FETCH p.book
        JOIN FETCH p.store
        WHERE a.scrapedAt = (
            SELECT MAX(a2.scrapedAt)
            FROM AvailabilitySnapshot a2
            WHERE a2.pair = p
        )
    """)
    List<AvailabilitySnapshot> findLatestPerPair();

    // Generalized history query — replaces findByBookIsbn(isbn, pageable), which
    // only fetched p.store and not p.book (fine when scoped to one isbn already —
    // not fine once history can span every book, since bookName needs that join).
    // Every filter here is optional: pass null for any one you don't want applied.
    @Query("""
        SELECT a FROM AvailabilitySnapshot a
        JOIN FETCH a.pair p
        JOIN FETCH p.book b
        JOIN FETCH p.store s
        WHERE (:isbn IS NULL OR b.isbn = :isbn)
          AND (:storeName IS NULL OR s.name = :storeName)
          AND (:status IS NULL OR a.status = :status)
        ORDER BY a.scrapedAt DESC
    """)
    List<AvailabilitySnapshot> findHistory(
            @Param("isbn") String isbn,
            @Param("storeName") String storeName,
            @Param("status") String status,
            Pageable pageable
    );

    // Used by TrackingService.toDto() to get last-scraped timestamp
    Optional<AvailabilitySnapshot> findTopByPairIdOrderByScrapedAtDesc(Long pairId);

    // Used during book/store deletion, and now also by "delete all history for
    // this pair" on the History page
    void deleteAllByPairId(Long pairId);
}