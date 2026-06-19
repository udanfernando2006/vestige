package io.github.udanfernando.vestige.dto;

import lombok.*;
import java.util.List;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class BookGroupDto {
    private String seriesName;     // null for standalone books
    private List<BookDto> books;
}
