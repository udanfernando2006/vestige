package io.github.udanfernando.vestige.dto;

import lombok.*;
import java.time.LocalDateTime;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class TrackingPairDto {
    private Long id;
    private BookDto book;
    private StoreDto store;
    private String productUrl;
    // The actual cached selector text — needed so the Tracking page can pre-fill
    // an edit box for an already-working pair, not just a NEEDS_SETUP one.
    private String priceSelector;
    private String stockSelector;
    private boolean selectorsCached;
    private String status;
    private LocalDateTime lastScrapedAt;
}