package io.github.udanfernando.vestige.service;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.*;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
class ScraperSettingsUpdateRequest {
    @JsonProperty("llm_discovery_enabled")
    private Boolean llmDiscoveryEnabled;

    @JsonProperty("llm_mode")
    private String llmMode;

    @JsonProperty("selector_api_base")
    private String selectorApiBase;

    @JsonProperty("selector_api_key")
    private String selectorApiKey;

    @JsonProperty("selector_model")
    private String selectorModel;

    @JsonProperty("direct_api_base")
    private String directApiBase;

    @JsonProperty("direct_api_key")
    private String directApiKey;

    @JsonProperty("direct_model")
    private String directModel;
}