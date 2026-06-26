package io.github.udanfernando.vestige.dto;

import lombok.*;
import java.math.BigDecimal;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class RunChangeDto {
    private Long pairId;
    private String bookName;
    private String storeName;
    private String fromStatus;
    private String toStatus;
    private BigDecimal fromPrice;
    private BigDecimal toPrice;
    private String productUrl;
}