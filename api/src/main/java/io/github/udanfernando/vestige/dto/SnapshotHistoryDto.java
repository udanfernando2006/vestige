package io.github.udanfernando.vestige.dto;

import lombok.*;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class SnapshotHistoryDto {
    private String storeName;
    private String status;
    private BigDecimal price;
    private LocalDateTime scrapedAt;
}