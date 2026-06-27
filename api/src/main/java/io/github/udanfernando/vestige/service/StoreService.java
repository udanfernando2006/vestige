package io.github.udanfernando.vestige.service;

import io.github.udanfernando.vestige.dto.*;
import io.github.udanfernando.vestige.entity.Store;
import io.github.udanfernando.vestige.entity.TrackingPair;
import io.github.udanfernando.vestige.exception.ResourceNotFoundException;
import io.github.udanfernando.vestige.repository.AvailabilitySnapshotRepository;
import io.github.udanfernando.vestige.repository.StoreRepository;
import io.github.udanfernando.vestige.repository.TrackingPairRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class StoreService {

    private final StoreRepository storeRepo;
    private final TrackingPairRepository pairRepo;
    private final AvailabilitySnapshotRepository snapshotRepo;

    @Transactional(readOnly = true)
    public List<StoreDto> getAll() {
        return storeRepo.findAll().stream()
                .map(this::toDto)
                .collect(Collectors.toList());
    }

    @Transactional
    public StoreDto create(StoreCreateDto dto) {
        // DataIntegrityViolationException from the UNIQUE constraint -> 409, via GlobalExceptionHandler
        Store store = Store.builder()
                .name(dto.getName())
                .baseUrl(dto.getBaseUrl())
                .build();
        return toDto(storeRepo.save(store));
    }

    // PATCH /api/stores/{id} — only applies fields actually present in the request.
    // searchUrlTemplate's "" = clear convention mirrors TrackingPairUpdateDto's
    // selector fields below and SettingsUpdateDto's secret fields.
    @Transactional
    public StoreDto update(Long id, StoreUpdateDto dto) {
        Store store = storeRepo.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Store not found: " + id));

        if (dto.getName() != null) {
            store.setName(dto.getName());
        }
        if (dto.getBaseUrl() != null) {
            store.setBaseUrl(dto.getBaseUrl());
        }
        if (dto.getSearchUrlTemplate() != null) {
            store.setSearchUrlTemplate(dto.getSearchUrlTemplate().isBlank() ? null : dto.getSearchUrlTemplate());
        }

        // DataIntegrityViolationException (renamed to a duplicate) -> 409, same as create()
        return toDto(storeRepo.save(store));
    }

    // DELETE /api/stores/{id} — cascades to every tracking pair for this store and
    // their snapshot history. Store.trackingPairs and TrackingPair.snapshots both
    // already carry cascade = CascadeType.ALL at the JPA level, so storeRepo.delete()
    // alone would likely cascade correctly — but BookService.delete() does this same
    // manual three-step sequence despite Book having the equivalent cascade available,
    // so this matches that established convention rather than relying on JPA cascade
    // ordering across two levels (Store -> TrackingPair -> AvailabilitySnapshot).
    @Transactional
    public void delete(Long id) {
        Store store = storeRepo.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Store not found: " + id));

        List<TrackingPair> pairs = pairRepo.findByStoreId(id);
        for (TrackingPair pair : pairs) {
            snapshotRepo.deleteAllByPairId(pair.getId());
        }
        pairRepo.deleteAll(pairs);
        storeRepo.delete(store);
    }

    private StoreDto toDto(Store s) {
        return StoreDto.builder()
                .id(s.getId())
                .name(s.getName())
                .baseUrl(s.getBaseUrl())
                .searchUrlTemplate(s.getSearchUrlTemplate())
                .build();
    }
}