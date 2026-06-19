package io.github.udanfernando.vestige.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.*;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class StoreCreateDto {
    @NotBlank(message = "Store name is required")
    private String name;

    @NotBlank(message = "Base URL is required")
    private String baseUrl;
}