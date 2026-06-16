package io.github.udanfernando.vestige.service;

import io.github.udanfernando.vestige.dto.*;
import io.github.udanfernando.vestige.entity.AvailabilitySnapshot;
import io.github.udanfernando.vestige.repository.AvailabilitySnapshotRepository;
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

    @Transactional(readOnly = true)
    public List<SnapshotHistoryDto> getHistory(String isbn, int limit) {
        return snapshotRepo.findByBookIsbn(isbn, PageRequest.of(0, limit)).stream()
                .map(s -> SnapshotHistoryDto.builder()
                        .storeName(s.getPair().getStore().getName())
                        .status(s.getStatus())
                        .price(s.getPrice())
                        .scrapedAt(s.getScrapedAt())
                        .build())
                .collect(Collectors.toList());
    }
}