package io.github.udanfernando.vestige.service;

import io.github.udanfernando.vestige.dto.*;
import io.github.udanfernando.vestige.entity.Store;
import io.github.udanfernando.vestige.repository.StoreRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class StoreService {

    private final StoreRepository storeRepo;

    @Transactional(readOnly = true)
    public List<StoreDto> getAll() {
        return storeRepo.findAll().stream()
                .map(this::toDto)
                .collect(Collectors.toList());
    }

    @Transactional
    public StoreDto create(StoreCreateDto dto) {
        // DataIntegrityViolationException from the UNIQUE constraint is caught
        // by GlobalExceptionHandler and returned as 409
        Store store = Store.builder()
                .name(dto.getName())
                .baseUrl(dto.getBaseUrl())
                .build();
        return toDto(storeRepo.save(store));
    }

    private StoreDto toDto(Store s) {
        return StoreDto.builder()
                .id(s.getId())
                .name(s.getName())
                .baseUrl(s.getBaseUrl())
                .build();
    }
}