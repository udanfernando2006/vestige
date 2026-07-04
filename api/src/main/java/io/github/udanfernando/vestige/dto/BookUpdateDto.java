package io.github.udanfernando.vestige.dto;

import lombok.*;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class BookUpdateDto {
    private String author;       // null = no change, "" = clear
    private String description;  // null = no change, "" = clear
}