package io.github.udanfernando.vestige.dto;

import lombok.*;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class RunSummaryDto {
    private String runId;
    private int totalPairs;
    private int changes;
    private int errors;
    private double durationSeconds;
    private String logPath;
}