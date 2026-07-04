package io.github.udanfernando.vestige.repository;

import io.github.udanfernando.vestige.entity.TrackingPair;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;

public interface TrackingPairRepository extends JpaRepository<TrackingPair, Long> {

    boolean existsByBookIdAndStoreId(Long bookId, Long storeId);

    // Used during book deletion
    List<TrackingPair> findByBookId(Long bookId);

    // Used during store deletion (new) — same cascade shape as findByBookId above
    List<TrackingPair> findByStoreId(Long storeId);

    // Eager-load book + store so the service can build DTOs without extra queries
    @EntityGraph(attributePaths = {"book", "store"})
    List<TrackingPair> findAllByOrderByIdAsc();

    @EntityGraph(attributePaths = {"book", "store"})
    List<TrackingPair> findByStatus(String status);
}
