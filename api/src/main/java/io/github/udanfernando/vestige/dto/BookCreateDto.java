package io.github.udanfernando.vestige.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import lombok.*;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class BookCreateDto {
    @NotBlank(message = "Book name is required")
    private String name;

    @NotBlank(message = "ISBN is required")
    private String isbn;

    @JsonProperty("isSeriesEntry")
    private boolean seriesEntry;

    private String seriesName;
    private String author;
    private String description;
}
