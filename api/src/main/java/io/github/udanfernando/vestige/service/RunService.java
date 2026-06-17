package io.github.udanfernando.vestige.service;

import tools.jackson.databind.ObjectMapper;
import io.github.udanfernando.vestige.dto.DiscoverResultDto;
import io.github.udanfernando.vestige.dto.RunSummaryDto;
import io.github.udanfernando.vestige.exception.PipelineExecutionException;
import io.github.udanfernando.vestige.exception.SelectorDiscoveryException;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.File;
import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class RunService {

    private final ObjectMapper objectMapper;

    @Value("${vestige.log-dir:logs}")
    private String logDir;

    @Value("${vestige.pipeline-command:python scraper/main.py}")
    private String pipelineCommand;

    @Value("${vestige.discover-command:python scraper/tools/discover_selectors.py}")
    private String discoverCommand;

    public List<RunSummaryDto> getRecentRuns() throws IOException {
        Path logPath = Paths.get(logDir);
        if (!Files.exists(logPath)) {
            return List.of();
        }

        List<Path> logFiles;
        try (var stream = Files.walk(logPath)) {
            logFiles = stream
                    .filter(p -> p.toString().endsWith(".json"))
                    .sorted(Comparator.reverseOrder())
                    .limit(50)
                    .collect(Collectors.toList());
        }

        List<RunSummaryDto> summaries = new ArrayList<>();
        for (Path file : logFiles) {
            try {
                Map<?, ?> raw = objectMapper.readValue(file.toFile(), Map.class);
                summaries.add(RunSummaryDto.builder()
                        .runId(str(raw.get("run_id")))
                        .totalPairs(toInt(raw.get("total_pairs")))
                        .changes(listSize(raw.get("changes")))
                        .errors(listSize(raw.get("errors")))
                        .durationSeconds(toDouble(raw.get("duration_seconds")))
                        .logPath(logPath.relativize(file).toString())
                        .build());
            } catch (Exception ignored) {
                // Skip malformed log files
            }
        }
        return summaries;
    }

    public RunSummaryDto trigger() throws IOException, InterruptedException {
        ProcessBuilder pb = new ProcessBuilder(pipelineCommand.split("\\s+"))
                .redirectErrorStream(true)
                .directory(new File(System.getProperty("user.dir")));
        pb.environment().put("PYTHONIOENCODING", "utf-8");

        Process process = pb.start();
        String output = new String(process.getInputStream().readAllBytes());
        int exitCode = process.waitFor();

        if (exitCode != 0) {
            throw new PipelineExecutionException("Pipeline exited with code " + exitCode, output);
        }

        List<RunSummaryDto> runs = getRecentRuns();
        return runs.isEmpty() ? null : runs.get(0);
    }

    public DiscoverResultDto discover(Long pairId) throws IOException, InterruptedException {
        String[] cmd = (discoverCommand + " --pair-id " + pairId).split("\\s+");
        ProcessBuilder pb = new ProcessBuilder(cmd)
                .redirectErrorStream(false)
                .directory(new File(System.getProperty("user.dir")));
        pb.environment().put("PYTHONIOENCODING", "utf-8");

        Process process = pb.start();
        String stdout = new String(process.getInputStream().readAllBytes());
        int exitCode = process.waitFor();

        if (exitCode != 0) {
            throw new SelectorDiscoveryException("Discovery failed", stdout);
        }

        DiscoverToolOutput parsed = objectMapper.readValue(stdout, DiscoverToolOutput.class);
        return DiscoverResultDto.builder()
                .pairId(pairId)
                .priceSelector(parsed.getPriceSelector())
                .stockSelector(parsed.getStockSelector())
                .priceSample(parsed.getPriceSample())
                .stockSample(parsed.getStockSample())
                .modelUsed(parsed.getModelUsed())
                .reason(parsed.getReason())
                .committed(parsed.isCommitted())
                .build();
    }

    private String str(Object o) { return o != null ? o.toString() : null; }
    private int toInt(Object o) { return o instanceof Number n ? n.intValue() : 0; }
    private double toDouble(Object o) { return o instanceof Number n ? n.doubleValue() : 0.0; }
    private int listSize(Object o) { return o instanceof List<?> list ? list.size() : 0; }
}