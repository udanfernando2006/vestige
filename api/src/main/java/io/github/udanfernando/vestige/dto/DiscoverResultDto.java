package io.github.udanfernando.vestige.dto;


import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.*;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class DiscoverResultDto {
    private Long pairId;

    @JsonProperty("price_selector")
    private String priceSelector;

    @JsonProperty("stock_selector")
    private String stockSelector;

    @JsonProperty("price_sample")
    private String priceSample;

    @JsonProperty("stock_sample")
    private String stockSample;

    @JsonProperty("model_used")
    private String modelUsed;

    private String reason;      // matches key name as-is
    private boolean committed;  // matches key name as-is
}