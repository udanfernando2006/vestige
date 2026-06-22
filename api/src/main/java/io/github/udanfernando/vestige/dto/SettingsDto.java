package io.github.udanfernando.vestige.dto;

import lombok.*;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class SettingsDto {
    private boolean llmDiscoveryEnabled;
    private String llmMode;
    private String selectorApiBase;
    private boolean selectorApiKeyConfigured;
    private String selectorApiKeyHint;
    private String selectorModel;
    private String directApiBase;
    private boolean directApiKeyConfigured;
    private String directApiKeyHint;
    private String directModel;
}