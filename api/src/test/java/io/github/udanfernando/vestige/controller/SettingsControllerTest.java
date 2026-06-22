package io.github.udanfernando.vestige.controller;

import tools.jackson.databind.ObjectMapper;
import io.github.udanfernando.vestige.dto.SettingsDto;
import io.github.udanfernando.vestige.dto.SettingsUpdateDto;
import io.github.udanfernando.vestige.exception.SettingsSyncException;
import io.github.udanfernando.vestige.service.SettingsService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(SettingsController.class)
class SettingsControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    // Spring Boot 4.x / spring-test 6.2+ standard component for test slice mocking
    @MockitoBean
    private SettingsService settingsService;

    @Test
    void shouldReturnSettingsSuccessfully() throws Exception {
        SettingsDto mockSettings = SettingsDto.builder()
                .llmDiscoveryEnabled(true)
                .llmMode("selector")
                .selectorApiBase("http://localhost:11434")
                .selectorApiKeyConfigured(true)
                .selectorApiKeyHint("••••99zY")
                .selectorModel("ollama/llama3.3")
                .directApiBase("https://api.openai.com/v1")
                .directApiKeyConfigured(false)
                .directApiKeyHint(null)
                .directModel("gpt-4o-mini")
                .build();

        when(settingsService.getSettings()).thenReturn(mockSettings);

        mockMvc.perform(get("/api/settings"))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.llmDiscoveryEnabled").value(true))
                .andExpect(jsonPath("$.llmMode").value("selector"))
                .andExpect(jsonPath("$.selectorApiBase").value("http://localhost:11434"))
                .andExpect(jsonPath("$.selectorApiKeyConfigured").value(true))
                .andExpect(jsonPath("$.selectorApiKeyHint").value("••••99zY"))
                .andExpect(jsonPath("$.selectorModel").value("ollama/llama3.3"))
                .andExpect(jsonPath("$.directApiBase").value("https://api.openai.com/v1"))
                .andExpect(jsonPath("$.directApiKeyConfigured").value(false))
                .andExpect(jsonPath("$.directApiKeyHint").isEmpty())
                .andExpect(jsonPath("$.directModel").value("gpt-4o-mini"));

        verify(settingsService, times(1)).getSettings();
    }

    @Test
    void shouldUpdateSettingsSuccessfully() throws Exception {
        SettingsUpdateDto updateDto = SettingsUpdateDto.builder()
                .llmDiscoveryEnabled(false)
                .llmMode("direct")
                .directModel("gpt-4o")
                .build();

        doNothing().when(settingsService).updateSettings(any(SettingsUpdateDto.class));

        mockMvc.perform(put("/api/settings")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(updateDto)))
                .andExpect(status().isNoContent());

        verify(settingsService, times(1)).updateSettings(any(SettingsUpdateDto.class));
    }

    @Test
    void shouldReturn502BadGatewayWhenUpstreamScraperServiceFails() throws Exception {
        when(settingsService.getSettings())
                .thenThrow(new SettingsSyncException("Could not reach scraper service: Connection refused"));

        mockMvc.perform(get("/api/settings"))
                .andExpect(status().isBadGateway())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.error").value("Could not reach scraper service: Connection refused"));

        verify(settingsService, times(1)).getSettings();
    }
}