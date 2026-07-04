package io.github.udanfernando.vestige.dto;

import lombok.*;
import java.util.List;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class RunDetailDto {
    private String runId;
    private int totalPairs;
    private int errors;
    private double durationSeconds;
    private List<RunChangeDto> changes;
}