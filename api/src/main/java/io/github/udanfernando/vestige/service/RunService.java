package io.github.udanfernando.vestige.service;

import tools.jackson.databind.ObjectMapper;
import io.github.udanfernando.vestige.dto.DiscoverResultDto;
import io.github.udanfernando.vestige.dto.RunSummaryDto;
import io.github.udanfernando.vestige.dto.RunChangeDto;
import io.github.udanfernando.vestige.dto.RunDetailDto;
import io.github.udanfernando.vestige.exception.ResourceNotFoundException;
import io.github.udanfernando.vestige.exception.PipelineExecutionException;
import io.github.udanfernando.vestige.exception.SelectorDiscoveryException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;

import java.io.IOException;
import java.net.http.HttpClient;
import java.nio.file.*;
import java.time.Duration;
import java.util.*;
import java.util.stream.Collectors;
import java.math.BigDecimal;

@Service
public class RunService {

    private final ObjectMapper objectMapper;
    private final RestClient restClient;

    @Value("${vestige.log-dir:logs}")
    private String logDir;

    public RunService(
            ObjectMapper objectMapper,
            @Value("${vestige.scraper-url:http://scraper-server:8000}") String scraperUrl) {
        this.objectMapper = objectMapper;

        // A full scrape run can take well over a minute. RestClient's default
        // timeouts are a few seconds — without this, a perfectly healthy long
        // run gets reported as a failure.
        HttpClient httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(5))
                .version(HttpClient.Version.HTTP_1_1)
                .build();
        JdkClientHttpRequestFactory factory = new JdkClientHttpRequestFactory(httpClient);
        factory.setReadTimeout(Duration.ofMinutes(3));

        this.restClient = RestClient.builder()
                .baseUrl(scraperUrl)
                .requestFactory(factory)
                .build();
    }

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

    public RunDetailDto getRunDetail(String runId) throws IOException {
        Path logPath = Paths.get(logDir);
        if (!Files.exists(logPath)) {
            throw new ResourceNotFoundException("Run not found: " + runId);
        }

        List<Path> logFiles;
        try (var stream = Files.walk(logPath)) {
            logFiles = stream.filter(p -> p.toString().endsWith(".json")).collect(Collectors.toList());
        }

        for (Path file : logFiles) {
            try {
                Map<?, ?> raw = objectMapper.readValue(file.toFile(), Map.class);
                if (runId.equals(str(raw.get("run_id")))) {
                    return toRunDetailDto(raw);
                }
            } catch (Exception ignored) {
                // Skip malformed log files, same tolerance as getRecentRuns()
            }
        }
        throw new ResourceNotFoundException("Run not found: " + runId);
    }

    private RunDetailDto toRunDetailDto(Map<?, ?> raw) {
        List<RunChangeDto> changes = new ArrayList<>();
        if (raw.get("changes") instanceof List<?> list) {
            for (Object o : list) {
                if (o instanceof Map<?, ?> c) {
                    changes.add(RunChangeDto.builder()
                            .pairId(toLong(c.get("pair_id")))
                            .bookName(str(c.get("book_name")))
                            .storeName(str(c.get("store_name")))
                            .fromStatus(str(c.get("from_status")))
                            .toStatus(str(c.get("to_status")))
                            .fromPrice(toBigDecimal(c.get("from_price")))
                            .toPrice(toBigDecimal(c.get("to_price")))
                            .productUrl(str(c.get("product_url")))
                            .build());
                }
            }
        }
        return RunDetailDto.builder()
                .runId(str(raw.get("run_id")))
                .totalPairs(toInt(raw.get("total_pairs")))
                .errors(listSize(raw.get("errors")))
                .durationSeconds(toDouble(raw.get("duration_seconds")))
                .changes(changes)
                .build();
    }

    public RunSummaryDto trigger() {
        try {
            restClient.post().uri("/run").retrieve().toBodilessEntity();
        } catch (RestClientResponseException e) {
            throw new PipelineExecutionException(
                    "Scraper service returned " + e.getStatusCode(), e.getResponseBodyAsString());
        } catch (Exception e) {
            throw new PipelineExecutionException(
                    "Could not reach scraper service: " + e.getMessage(), "");
        }

        try {
            List<RunSummaryDto> runs = getRecentRuns();
            return runs.isEmpty() ? null : runs.get(0);
        } catch (IOException e) {
            throw new PipelineExecutionException("Pipeline ran but log read failed: " + e.getMessage(), "");
        }
    }

    public DiscoverResultDto discover(Long pairId) {
        String stdoutJson;
        try {
            stdoutJson = restClient.post()
                    .uri("/discover/{id}", pairId)
                    .retrieve()
                    .body(String.class);
        } catch (RestClientResponseException e) {
            throw new SelectorDiscoveryException(
                    "Discovery failed (" + e.getStatusCode() + ")", e.getResponseBodyAsString());
        } catch (Exception e) {
            throw new SelectorDiscoveryException("Could not reach scraper service: " + e.getMessage(), "");
        }

        DiscoverToolOutput parsed = objectMapper.readValue(stdoutJson, DiscoverToolOutput.class);
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
    private Long toLong(Object o) { return o instanceof Number n ? n.longValue() : null; }
    private BigDecimal toBigDecimal(Object o) { return o instanceof Number n ? BigDecimal.valueOf(n.doubleValue()) : null; }
}