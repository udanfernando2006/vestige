package io.github.udanfernando.vestige.dto;

import lombok.*;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class StoreDto {
    private Long id;
    private String name;
    private String baseUrl;
    private String searchUrlTemplate; // null = undiscovered; the Crawler caches one here on first successful search
}