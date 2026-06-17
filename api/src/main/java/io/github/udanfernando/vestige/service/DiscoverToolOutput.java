package io.github.udanfernando.vestige.service;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.*;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor
class DiscoverToolOutput {
    @JsonProperty("price_selector") private String priceSelector;
    @JsonProperty("stock_selector") private String stockSelector;
    @JsonProperty("price_sample") private String priceSample;
    @JsonProperty("stock_sample") private String stockSample;
    @JsonProperty("model_used") private String modelUsed;
    private String reason;
    private boolean committed;
}