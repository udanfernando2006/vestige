package io.github.udanfernando.vestige.service;

import io.github.udanfernando.vestige.dto.*;
import io.github.udanfernando.vestige.exception.ResourceNotFoundException;
import io.github.udanfernando.vestige.repository.AvailabilitySnapshotRepository;
import io.github.udanfernando.vestige.repository.TrackingPairRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class AvailabilityService {

    private final AvailabilitySnapshotRepository snapshotRepo;
    private final TrackingPairRepository pairRepo; // new dependency — Lombok wires it automatically

    @Transactional(readOnly = true)
    public List<AvailabilityDto> getCurrentStatus() {
        return snapshotRepo.findLatestPerPair().stream()
                .map(s -> AvailabilityDto.builder()
                        .pairId(s.getPair().getId())
                        .bookName(s.getPair().getBook().getName())
                        .storeName(s.getPair().getStore().getName())
                        .status(s.getStatus())
                        .price(s.getPrice())
                        .productUrl(s.getPair().getProductUrl())
                        .scrapedAt(s.getScrapedAt())
                        .build())
                .collect(Collectors.toList());
    }

    // GET /api/availability/history — every filter optional; null means "don't
    // filter on this." Called with everything null for the History page's default
    // just-show-everything view.
    @Transactional(readOnly = true)
    public List<SnapshotHistoryDto> getHistory(String isbn, String storeName, String status, int limit) {
        return snapshotRepo.findHistory(isbn, storeName, status, PageRequest.of(0, limit)).stream()
                .map(s -> SnapshotHistoryDto.builder()
                        .id(s.getId())
                        .pairId(s.getPair().getId())
                        .bookName(s.getPair().getBook().getName())
                        .storeName(s.getPair().getStore().getName())
                        .status(s.getStatus())
                        .price(s.getPrice())
                        .scrapedAt(s.getScrapedAt())
                        .build())
                .collect(Collectors.toList());
    }

    // DELETE /api/availability/{id} — a single snapshot row.
    @Transactional
    public void deleteSnapshot(Long id) {
        if (!snapshotRepo.existsById(id)) {
            throw new ResourceNotFoundException("Snapshot not found: " + id);
        }
        snapshotRepo.deleteById(id);
    }

    // DELETE /api/availability/pair/{pairId} — every snapshot for one tracking
    // pair. Doesn't touch the pair itself or its cached selectors, only its
    // history. Deliberately not exposed at the book level.
    @Transactional
    public void deleteHistoryForPair(Long pairId) {
        if (!pairRepo.existsById(pairId)) {
            throw new ResourceNotFoundException("Tracking pair not found: " + pairId);
        }
        snapshotRepo.deleteAllByPairId(pairId);
    }
}