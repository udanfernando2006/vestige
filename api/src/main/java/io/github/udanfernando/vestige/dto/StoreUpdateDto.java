package io.github.udanfernando.vestige.dto;

import lombok.*;

// PATCH semantics, every field optional. searchUrlTemplate follows the same
// "" = explicit clear / omitted = no change convention SettingsUpdateDto's
// secret fields already use. Clearing it puts the store back into
// "undiscovered," and the Crawler's two-phase discovery re-caches a fresh
// template on the next run for any pair without a product URL yet.
@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class StoreUpdateDto {
    private String name;
    private String baseUrl;
    private String searchUrlTemplate;
}
