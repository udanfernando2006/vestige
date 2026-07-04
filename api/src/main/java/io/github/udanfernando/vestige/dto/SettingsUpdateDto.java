package io.github.udanfernando.vestige.dto;

import lombok.*;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class SettingsUpdateDto {
    private Boolean llmDiscoveryEnabled;
    private String llmMode;
    private String selectorApiBase;
    private String selectorApiKey;
    private String selectorModel;
    private String directApiBase;
    private String directApiKey;
    private String directModel;
    private Integer scrapeIntervalHours; // null = no change; 0 = disable; >0 = set
}