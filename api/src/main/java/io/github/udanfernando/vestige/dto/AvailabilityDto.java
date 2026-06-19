package io.github.udanfernando.vestige.dto;

import lombok.*;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class AvailabilityDto {
    private Long pairId;
    private String bookName;
    private String storeName;
    private String status;
    private BigDecimal price;
    private String productUrl;
    private LocalDateTime scrapedAt;
}