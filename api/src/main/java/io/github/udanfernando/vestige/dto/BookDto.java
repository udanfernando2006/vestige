package io.github.udanfernando.vestige.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.*;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class BookDto {
    private Long id;
    private String name;
    private String isbn;
    @JsonProperty("isSeriesEntry")
    private boolean seriesEntry;
    private Long seriesId;
    private String seriesName;
}
