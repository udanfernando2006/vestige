package io.github.udanfernando.vestige.dto;

import lombok.*;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class SeriesUpdateDto {
    private String name;        // omitted = no rename; blank string rejected in service
    private String author;      // null = no change, "" = clear
    private String description; // null = no change, "" = clear
}