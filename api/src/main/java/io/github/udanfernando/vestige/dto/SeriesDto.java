package io.github.udanfernando.vestige.dto;

import lombok.*;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class SeriesDto {
    private Long id;
    private String name;
    private int bookCount;
    private String author;
    private String description;
}