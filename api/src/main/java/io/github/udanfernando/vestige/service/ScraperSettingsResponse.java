package io.github.udanfernando.vestige.service;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.*;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor
class ScraperSettingsResponse {
    @JsonProperty("llm_discovery_enabled")
    private boolean llmDiscoveryEnabled;

    @JsonProperty("llm_mode")
    private String llmMode;

    @JsonProperty("selector_api_base")
    private String selectorApiBase;

    @JsonProperty("selector_api_key_configured")
    private boolean selectorApiKeyConfigured;

    @JsonProperty("selector_api_key_hint")
    private String selectorApiKeyHint;

    @JsonProperty("selector_model")
    private String selectorModel;

    @JsonProperty("direct_api_base")
    private String directApiBase;

    @JsonProperty("direct_api_key_configured")
    private boolean directApiKeyConfigured;

    @JsonProperty("direct_api_key_hint")
    private String directApiKeyHint;

    @JsonProperty("direct_model")
    private String directModel;

    @JsonProperty("scrape_interval_hours")
    private Integer scrapeIntervalHours;

}
