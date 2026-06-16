package io.github.udanfernando.vestige.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.*;

// Field names use @JsonProperty to match the snake_case keys
// that the Python local_logger writes to JSON files
@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class RunSummaryDto {
    @JsonProperty("run_id")
    private String runId;

    @JsonProperty("total_pairs")
    private int totalPairs;

    // "changes" is the size of the changes array in the log file
    private int changes;

    // "errors" is the size of the errors array in the log file
    private int errors;

    @JsonProperty("duration_seconds")
    private double durationSeconds;

    // Relative path to the log file — populated only for GET /api/runs
    private String logPath;
}