package io.github.udanfernando.vestige.controller;

import io.github.udanfernando.vestige.dto.DiscoverResultDto;
import io.github.udanfernando.vestige.dto.RunSummaryDto;
import io.github.udanfernando.vestige.dto.RunChangeDto;
import io.github.udanfernando.vestige.dto.RunDetailDto;
import io.github.udanfernando.vestige.exception.PipelineExecutionException;
import io.github.udanfernando.vestige.exception.SelectorDiscoveryException;
import io.github.udanfernando.vestige.exception.ResourceNotFoundException;
import io.github.udanfernando.vestige.service.RunService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(RunController.class)
class RunControllerTest {

    @Autowired private MockMvc mockMvc;

    @MockitoBean
    private RunService runService;

    @Test
    void getRecentRuns_returnsLogSummaries() throws Exception {
        RunSummaryDto run = RunSummaryDto.builder()
                .runId("2026-05-16T08:00:00Z").totalPairs(12).changes(1).errors(0)
                .durationSeconds(47.2).logPath("2026/05/16/08-00-00.json").build();

        when(runService.getRecentRuns()).thenReturn(List.of(run));

        mockMvc.perform(get("/api/runs"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].runId").value("2026-05-16T08:00:00Z"))
                .andExpect(jsonPath("$[0].totalPairs").value(12));
    }

    @Test
    void getRunDetail_returnsChanges() throws Exception {
        RunChangeDto change = RunChangeDto.builder()
                .pairId(2L).bookName("Sword of Destiny").storeName("vijitha_yapa")
                .fromStatus("IN_STOCK").toStatus("OUT_OF_STOCK")
                .fromPrice(new java.math.BigDecimal("1500.00"))
                .toPrice(null)
                .productUrl("https://vijithayapa.com/books/sword-of-destiny")
                .build();

        RunDetailDto detail = RunDetailDto.builder()
                .runId("2026-05-16T08:00:00Z").totalPairs(12).errors(0).durationSeconds(47.2)
                .changes(List.of(change))
                .build();

        when(runService.getRunDetail("2026-05-16T08:00:00Z")).thenReturn(detail);

        mockMvc.perform(get("/api/runs/2026-05-16T08:00:00Z"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.changes[0].bookName").value("Sword of Destiny"))
                .andExpect(jsonPath("$.changes[0].fromStatus").value("IN_STOCK"))
                .andExpect(jsonPath("$.changes[0].toStatus").value("OUT_OF_STOCK"))
                .andExpect(jsonPath("$.changes[0].toPrice").doesNotExist()); // NON_NULL omits it, doesn't send null
    }

    @Test
    void getRunDetail_unknownRunId_returns404() throws Exception {
        when(runService.getRunDetail("does-not-exist"))
                .thenThrow(new ResourceNotFoundException("Run not found: does-not-exist"));

        mockMvc.perform(get("/api/runs/does-not-exist"))
                .andExpect(status().isNotFound());
    }

    @Test
    void trigger_success_returnsSummary() throws Exception {
        RunSummaryDto run = RunSummaryDto.builder()
                .runId("2026-05-16T12:30:00Z").totalPairs(12).changes(1).errors(0)
                .durationSeconds(43.1).build();

        when(runService.trigger()).thenReturn(run);

        mockMvc.perform(post("/api/runs/trigger"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.runId").value("2026-05-16T12:30:00Z"));
    }

    @Test
    void trigger_noLogFileFound_returnsMessage() throws Exception {
        when(runService.trigger()).thenReturn(null);

        mockMvc.perform(post("/api/runs/trigger"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.message").value("Pipeline completed but no log file found"));
    }

    @Test
    void trigger_pipelineFails_returns500WithOutput() throws Exception {
        when(runService.trigger())
                .thenThrow(new PipelineExecutionException("Pipeline exited with code 1", "Traceback..."));

        mockMvc.perform(post("/api/runs/trigger"))
                .andExpect(status().isInternalServerError())
                .andExpect(jsonPath("$.output").value("Traceback..."));
    }

    @Test
    void discover_success_returnsSelectors() throws Exception {
        DiscoverResultDto result = DiscoverResultDto.builder()
                .pairId(3L)
                .priceSelector("div[class*='price'] span")
                .stockSelector("div[class*='availability'] span")
                .priceSample("LKR 1,500.00")
                .stockSample("In Stock")
                .modelUsed("anthropic/claude-haiku-4-5")
                .committed(false)
                .build();

        when(runService.discover(eq(3L))).thenReturn(result);

        mockMvc.perform(post("/api/runs/discover/3"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.priceSelector").value("div[class*='price'] span"))
                .andExpect(jsonPath("$.modelUsed").value("anthropic/claude-haiku-4-5"));
    }

    @Test
    void discover_validationFailed_returns422() throws Exception {
        when(runService.discover(eq(3L)))
                .thenThrow(new SelectorDiscoveryException("Discovery failed",
                        "{\"reason\":\"stock_selector_returned_no_match\"}"));

        mockMvc.perform(post("/api/runs/discover/3"))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.output").exists());
    }
}