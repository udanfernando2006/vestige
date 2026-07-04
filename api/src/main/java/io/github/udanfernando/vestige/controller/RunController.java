package io.github.udanfernando.vestige.controller;

import io.github.udanfernando.vestige.dto.DiscoverResultDto;
import io.github.udanfernando.vestige.dto.RunSummaryDto;
import io.github.udanfernando.vestige.dto.RunDetailDto;
import io.github.udanfernando.vestige.exception.PipelineExecutionException;
import io.github.udanfernando.vestige.exception.SelectorDiscoveryException;
import io.github.udanfernando.vestige.service.RunService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.io.IOException;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/runs")
@RequiredArgsConstructor
public class RunController {

    private final RunService runService;

    @GetMapping
    public ResponseEntity<List<RunSummaryDto>> getRecentRuns() throws IOException {
        return ResponseEntity.ok(runService.getRecentRuns());
    }

    @GetMapping("/{runId}")
    public ResponseEntity<RunDetailDto> getRunDetail(@PathVariable String runId) throws IOException {
        return ResponseEntity.ok(runService.getRunDetail(runId));
    }

    @PostMapping("/trigger")
    public ResponseEntity<?> trigger() throws IOException, InterruptedException {
        RunSummaryDto summary = runService.trigger();
        if (summary == null) {
            return ResponseEntity.ok(Map.of("message", "Pipeline completed but no log file found"));
        }
        return ResponseEntity.ok(summary);
    }

    @PostMapping("/discover/{pairId}")
    public ResponseEntity<DiscoverResultDto> discover(@PathVariable Long pairId) throws IOException, InterruptedException {
        return ResponseEntity.ok(runService.discover(pairId));
    }

    // Scoped to this controller — these statuses don't apply anywhere else in the API
    @ExceptionHandler(PipelineExecutionException.class)
    public ResponseEntity<Map<String, String>> handlePipelineFailure(PipelineExecutionException ex) {
        return ResponseEntity.status(500).body(Map.of("error", ex.getMessage(), "output", ex.getOutput()));
    }

    @ExceptionHandler(SelectorDiscoveryException.class)
    public ResponseEntity<Map<String, String>> handleDiscoveryFailure(SelectorDiscoveryException ex) {
        return ResponseEntity.status(422).body(Map.of("error", ex.getMessage(), "output", ex.getOutput()));
    }
}