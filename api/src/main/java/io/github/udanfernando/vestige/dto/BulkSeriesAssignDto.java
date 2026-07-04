// BulkSeriesAssignDto.java
package io.github.udanfernando.vestige.dto;

import jakarta.validation.constraints.NotEmpty;
import lombok.*;

import java.util.List;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class BulkSeriesAssignDto {
    @NotEmpty(message = "At least one book must be selected")
    private List<Long> bookIds;

    // Exactly one of these two must be provided — validated in the service,
    // since jakarta.validation doesn't cleanly express "exactly one of" here.
    private Long seriesId;
    private String newSeriesName;
}