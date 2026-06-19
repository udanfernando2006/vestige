package io.github.udanfernando.vestige.service;

import io.github.udanfernando.vestige.dto.*;
import io.github.udanfernando.vestige.entity.*;
import io.github.udanfernando.vestige.exception.ResourceNotFoundException;
import io.github.udanfernando.vestige.repository.*;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class TrackingService {

    private final TrackingPairRepository pairRepo;
    private final BookRepository bookRepo;
    private final StoreRepository storeRepo;
    private final AvailabilitySnapshotRepository snapshotRepo;

    @Transactional(readOnly = true)
    public List<TrackingPairDto> getAll() {
        return pairRepo.findAllByOrderByIdAsc().stream()
                .map(this::toDto)
                .collect(Collectors.toList());
    }

    @Transactional(readOnly = true)
    public List<TrackingPairDto> getNeedsSetup() {
        return pairRepo.findByStatus("NEEDS_SETUP").stream()
                .map(this::toDto)
                .collect(Collectors.toList());
    }

    @Transactional
    public TrackingPairDto create(TrackingPairCreateDto dto) {
        Book book = bookRepo.findByIsbn(dto.getIsbn())
                .orElseThrow(() -> new ResourceNotFoundException("Book not found with ISBN: " + dto.getIsbn()));

        Store store = storeRepo.findByName(dto.getStoreName())
                .orElseThrow(() -> new ResourceNotFoundException("Store not found: " + dto.getStoreName()));

        // UNIQUE(book_id, store_id) — DataIntegrityViolationException → 409
        TrackingPair pair = TrackingPair.builder()
                .book(book)
                .store(store)
                .productUrl(dto.getProductUrl())
                .status("PENDING")
                .build();

        return toDto(pairRepo.save(pair));
    }

    // PATCH /api/tracking/{id} — only applies non-null fields
    @Transactional
    public TrackingPairDto update(Long id, TrackingPairUpdateDto dto) {
        TrackingPair pair = pairRepo.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Tracking pair not found: " + id));

        if (dto.getProductUrl() != null)    pair.setProductUrl(dto.getProductUrl());
        if (dto.getPriceSelector() != null) pair.setPriceSelector(dto.getPriceSelector());
        if (dto.getStockSelector() != null) pair.setStockSelector(dto.getStockSelector());

        // Explicit status update (e.g. SKIP, re-enable) takes priority
        if (dto.getStatus() != null) {
            pair.setStatus(dto.getStatus());
        } else {
            // Auto-transition: both selectors now present + pair is blocked
            boolean bothSelectors = pair.getPriceSelector() != null
                    && pair.getStockSelector() != null;
            if (bothSelectors && "NEEDS_SETUP".equals(pair.getStatus())) {
                pair.setStatus("PENDING");
                pair.setSelectorFoundAt(LocalDateTime.now());
            }
        }

        return toDto(pairRepo.save(pair));
    }

    private TrackingPairDto toDto(TrackingPair p) {
        LocalDateTime lastScraped = snapshotRepo
                .findTopByPairIdOrderByScrapedAtDesc(p.getId())
                .map(AvailabilitySnapshot::getScrapedAt)
                .orElse(null);

        return TrackingPairDto.builder()
                .id(p.getId())
                .book(BookDto.builder()
                        .id(p.getBook().getId())
                        .name(p.getBook().getName())
                        .isbn(p.getBook().getIsbn())
                        .build())
                .store(StoreDto.builder()
                        .id(p.getStore().getId())
                        .name(p.getStore().getName())
                        .build())
                .productUrl(p.getProductUrl())
                .selectorsCached(p.getPriceSelector() != null && p.getStockSelector() != null)
                .status(p.getStatus())
                .lastScrapedAt(lastScraped)
                .build();
    }
}