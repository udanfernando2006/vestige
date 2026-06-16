package io.github.udanfernando.vestige.dto;

import lombok.*;
import java.time.LocalDateTime;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class TrackingPairDto {
    private Long id;
    private BookDto book;
    private StoreDto store;
    private String productUrl;
    private boolean selectorsCached;
    private String status;
    private LocalDateTime lastScrapedAt;
}