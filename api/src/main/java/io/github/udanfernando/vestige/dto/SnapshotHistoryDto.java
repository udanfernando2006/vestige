package io.github.udanfernando.vestige.dto;

import lombok.*;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class SnapshotHistoryDto {
    private Long id;        // the snapshot's own row id — needed to target a single delete
    private Long pairId;    // needed to target "delete all history for this pair"
    private String bookName; // only meaningful once history can span more than one book
    private String storeName;
    private String status;
    private BigDecimal price;
    private LocalDateTime scrapedAt;
}