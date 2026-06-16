package io.github.udanfernando.vestige.repository;

import io.github.udanfernando.vestige.entity.AvailabilitySnapshot;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import java.util.List;
import java.util.Optional;

public interface AvailabilitySnapshotRepository extends JpaRepository<AvailabilitySnapshot, Long> {

    // Latest snapshot per tracking pair — used for the dashboard current-status view
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

    // Full history for a book across all stores, newest first, with optional limit
    @Query("""
        SELECT a FROM AvailabilitySnapshot a
        JOIN FETCH a.pair p
        JOIN FETCH p.store
        WHERE p.book.isbn = :isbn
        ORDER BY a.scrapedAt DESC
    """)
    List<AvailabilitySnapshot> findByBookIsbn(@Param("isbn") String isbn, Pageable pageable);

    // Used by TrackingService.toDto() to get last-scraped timestamp
    Optional<AvailabilitySnapshot> findTopByPairIdOrderByScrapedAtDesc(Long pairId);

    // Used during book deletion to remove snapshots before their pairs
    void deleteAllByPairId(Long pairId);
}
