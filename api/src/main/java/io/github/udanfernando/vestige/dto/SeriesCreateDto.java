package io.github.udanfernando.vestige.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.*;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class SeriesCreateDto {
    @NotBlank(message = "Series name is required")
    private String name;
    private String author;
    private String description;
}