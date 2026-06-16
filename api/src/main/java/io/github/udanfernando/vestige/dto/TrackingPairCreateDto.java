package io.github.udanfernando.vestige.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.*;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class TrackingPairCreateDto {
    @NotBlank(message = "ISBN is required")
    private String isbn;

    @NotBlank(message = "Store name is required")
    private String storeName;

    private String productUrl;   // optional; null triggers crawler on first run
}