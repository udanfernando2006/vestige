package io.github.udanfernando.vestige.controller;

import tools.jackson.databind.ObjectMapper;
import io.github.udanfernando.vestige.dto.*;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.stream.*;

@RestController
@RequestMapping("/api/runs")
@RequiredArgsConstructor
public class RunController {

    private final ObjectMapper objectMapper;

    @Value("${vestige.log-dir:logs}")
    private String logDir;

    @Value("${vestige.pipeline-command:python scraper/main.py}")
    private String pipelineCommand;

    @Value("${vestige.discover-command:python scraper/tools/discover_selectors.py}")
    private String discoverCommand;

    // GET /api/runs — read summaries from local log files, newest first
    @GetMapping
    public ResponseEntity<List<RunSummaryDto>> getRecentRuns() throws IOException {
        Path logPath = Paths.get(logDir);
        if (!Files.exists(logPath)) {
            return ResponseEntity.ok(List.of());
        }

        List<Path> logFiles = Files.walk(logPath)
                .filter(p -> p.toString().endsWith(".json"))
                .sorted(Comparator.reverseOrder())
                .limit(50)
                .collect(Collectors.toList());

        List<RunSummaryDto> summaries = new ArrayList<>();
        for (Path file : logFiles) {
            try {
                Map<?, ?> raw = objectMapper.readValue(file.toFile(), Map.class);
                RunSummaryDto dto = RunSummaryDto.builder()
                        .runId(str(raw.get("run_id")))
                        .totalPairs(toInt(raw.get("total_pairs")))
                        .changes(listSize(raw.get("changes")))
                        .errors(listSize(raw.get("errors")))
                        .durationSeconds(toDouble(raw.get("duration_seconds")))
                        .logPath(logPath.relativize(file).toString())
                        .build();
                summaries.add(dto);
            } catch (Exception ignored) {
                // Skip malformed log files
            }
        }
        return ResponseEntity.ok(summaries);
    }

    // POST /api/runs/trigger — invoke the Python pipeline and return the summary
    @PostMapping("/trigger")
    public ResponseEntity<?> trigger() throws IOException, InterruptedException {
        String[] cmd = pipelineCommand.split("\\s+");
        ProcessBuilder pb = new ProcessBuilder(cmd)
                .redirectErrorStream(true)
                .directory(new File(System.getProperty("user.dir")));

        pb.environment().put("PYTHONIOENCODING", "utf-8");

        Process process = pb.start();
        String output = new String(process.getInputStream().readAllBytes());
        int exitCode = process.waitFor();

        if (exitCode != 0) {
            return ResponseEntity.status(500)
                    .body(Map.of("error", "Pipeline exited with code " + exitCode, "output", output));
        }

        List<RunSummaryDto> runs = getRecentRuns().getBody();
        if (runs == null || runs.isEmpty()) {
            return ResponseEntity.ok(Map.of("message", "Pipeline completed but no log file found"));
        }
        return ResponseEntity.ok(runs.get(0));
    }

    // POST /api/runs/discover/{pairId} — invoke discover_selectors.py and return its JSON output
    @PostMapping("/discover/{pairId}")
    public ResponseEntity<?> discover(@PathVariable Long pairId) throws IOException, InterruptedException {
        String[] cmd = (discoverCommand + " --pair-id " + pairId).split("\\s+");
        ProcessBuilder pb = new ProcessBuilder(cmd)
                .redirectErrorStream(false)   // keep stdout and stderr separate
                .directory(new File(System.getProperty("user.dir")));

        pb.environment().put("PYTHONIOENCODING", "utf-8");

        Process process = pb.start();
        String stdout = new String(process.getInputStream().readAllBytes());
        int exitCode = process.waitFor();

        if (exitCode != 0) {
            return ResponseEntity.status(422)
                    .body(Map.of("error", "Discovery failed", "output", stdout));
        }

        try {
            DiscoverResultDto result = objectMapper.readValue(stdout, DiscoverResultDto.class);
            result.setPairId(pairId);
            return ResponseEntity.ok(result);
        } catch (Exception e) {
            return ResponseEntity.status(500)
                    .body(Map.of("error", "Could not parse discovery output", "raw", stdout));
        }
    }

    // ── Helpers for reading untyped JSON from log files ──────────────────────

    private String str(Object o) {
        return o != null ? o.toString() : null;
    }

    private int toInt(Object o) {
        if (o instanceof Number n) return n.intValue();
        return 0;
    }

    private double toDouble(Object o) {
        if (o instanceof Number n) return n.doubleValue();
        return 0.0;
    }

    private int listSize(Object o) {
        if (o instanceof List<?> list) return list.size();
        return 0;
    }
}