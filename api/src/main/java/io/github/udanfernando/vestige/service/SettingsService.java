package io.github.udanfernando.vestige.service;

import io.github.udanfernando.vestige.dto.SettingsDto;
import io.github.udanfernando.vestige.dto.SettingsUpdateDto;
import io.github.udanfernando.vestige.exception.SettingsSyncException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;

import java.net.http.HttpClient;
import java.time.Duration;

@Service
public class SettingsService {

    private final RestClient restClient;

    public SettingsService(@Value("${vestige.scraper-url:http://scraper-server:8000}") String scraperUrl) {
        // Same HTTP/1.1 pin as RunService, to avoid uvicorn logging an h2c
        // upgrade warning on every call. Config calls are quick, so a much
        // shorter read timeout than RunService's 3-minute pipeline allowance.
        HttpClient httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(5))
                .version(HttpClient.Version.HTTP_1_1)
                .build();
        JdkClientHttpRequestFactory factory = new JdkClientHttpRequestFactory(httpClient);
        factory.setReadTimeout(Duration.ofSeconds(10));

        this.restClient = RestClient.builder().baseUrl(scraperUrl).requestFactory(factory).build();
    }

    public SettingsDto getSettings() {
        ScraperSettingsResponse r;
        try {
            r = restClient.get().uri("/config").retrieve().body(ScraperSettingsResponse.class);
        } catch (RestClientResponseException e) {
            throw new SettingsSyncException("Scraper service returned " + e.getStatusCode());
        } catch (Exception e) {
            throw new SettingsSyncException("Could not reach scraper service: " + e.getMessage());
        }
        return SettingsDto.builder()
                .llmDiscoveryEnabled(r.isLlmDiscoveryEnabled())
                .llmMode(r.getLlmMode())
                .selectorApiBase(r.getSelectorApiBase())
                .selectorApiKeyConfigured(r.isSelectorApiKeyConfigured())
                .selectorApiKeyHint(r.getSelectorApiKeyHint())
                .selectorModel(r.getSelectorModel())
                .directApiBase(r.getDirectApiBase())
                .directApiKeyConfigured(r.isDirectApiKeyConfigured())
                .directApiKeyHint(r.getDirectApiKeyHint())
                .directModel(r.getDirectModel())
                .build();
    }

    public void updateSettings(SettingsUpdateDto dto) {
        ScraperSettingsUpdateRequest body = ScraperSettingsUpdateRequest.builder()
                .llmDiscoveryEnabled(dto.getLlmDiscoveryEnabled())
                .llmMode(dto.getLlmMode())
                .selectorApiBase(dto.getSelectorApiBase())
                .selectorApiKey(dto.getSelectorApiKey())
                .selectorModel(dto.getSelectorModel())
                .directApiBase(dto.getDirectApiBase())
                .directApiKey(dto.getDirectApiKey())
                .directModel(dto.getDirectModel())
                .build();
        try {
            restClient.put().uri("/config").body(body).retrieve().toBodilessEntity();
        } catch (RestClientResponseException e) {
            throw new SettingsSyncException("Scraper service rejected the update (" + e.getStatusCode() + "): " + e.getResponseBodyAsString());
        } catch (Exception e) {
            throw new SettingsSyncException("Could not reach scraper service: " + e.getMessage());
        }
    }
}