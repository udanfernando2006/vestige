package io.github.udanfernando.vestige.dto;

import lombok.*;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class DiscoverResultDto {
    private Long pairId;
    private String priceSelector;
    private String stockSelector;
    private String priceSample;
    private String stockSample;
    private String modelUsed;
    private String reason;      // populated only on failure
    private boolean committed;
}