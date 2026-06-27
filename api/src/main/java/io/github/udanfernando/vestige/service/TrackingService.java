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

    // PATCH /api/tracking/{id} — only applies non-null fields.
    //
    // priceSelector/stockSelector now follow the "" = explicit clear, omitted = no
    // change convention SettingsUpdateDto's secret fields already use — previously
    // there was no way to clear a selector here at all, since a plain null check
    // can't distinguish "leave it" from "blank it out."
    //
    // Clearing a selector now surfaces immediately as NEEDS_SETUP rather than
    // waiting for the Orchestrator to notice on its own next run. It would notice
    // eventually either way — determine_path() already routes a pair with a
    // missing selector back through discovery or Path D regardless of what status
    // this leaves it in — but setting NEEDS_SETUP here means the Tracking page's
    // amber banner reflects the change the moment you make it.
    @Transactional
    public TrackingPairDto update(Long id, TrackingPairUpdateDto dto) {
        TrackingPair pair = pairRepo.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Tracking pair not found: " + id));

        if (dto.getProductUrl() != null) pair.setProductUrl(dto.getProductUrl());

        boolean selectorsTouched = false;
        if (dto.getPriceSelector() != null) {
            pair.setPriceSelector(dto.getPriceSelector().isBlank() ? null : dto.getPriceSelector());
            selectorsTouched = true;
        }
        if (dto.getStockSelector() != null) {
            pair.setStockSelector(dto.getStockSelector().isBlank() ? null : dto.getStockSelector());
            selectorsTouched = true;
        }

        if (dto.getStatus() != null) {
            // Explicit status update (e.g. SKIP, re-enable) always takes priority
            // over the auto-transition below.
            pair.setStatus(dto.getStatus());
        } else if (selectorsTouched) {
            boolean bothSelectors = pair.getPriceSelector() != null && pair.getStockSelector() != null;
            if (bothSelectors) {
                // Both present — same auto-transition as before this update: only
                // fires if the pair was blocked on missing selectors.
                if ("NEEDS_SETUP".equals(pair.getStatus())) {
                    pair.setStatus("PENDING");
                    pair.setSelectorFoundAt(LocalDateTime.now());
                }
            } else if (!"SKIP".equals(pair.getStatus())) {
                // At least one selector was just cleared. Leave SKIP pairs alone —
                // a deliberate user choice this shouldn't override — but everything
                // else goes back to NEEDS_SETUP immediately.
                pair.setStatus("NEEDS_SETUP");
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
                .priceSelector(p.getPriceSelector())
                .stockSelector(p.getStockSelector())
                .selectorsCached(p.getPriceSelector() != null && p.getStockSelector() != null)
                .status(p.getStatus())
                .lastScrapedAt(lastScraped)
                .build();
    }
}