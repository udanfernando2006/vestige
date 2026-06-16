package io.github.udanfernando.vestige.dto;

import lombok.*;

// All fields are optional — only non-null fields are applied in the PATCH
@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class TrackingPairUpdateDto {
    private String productUrl;
    private String priceSelector;
    private String stockSelector;
    private String status;
}