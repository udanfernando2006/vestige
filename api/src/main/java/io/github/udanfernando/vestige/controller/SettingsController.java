package io.github.udanfernando.vestige.controller;

import io.github.udanfernando.vestige.dto.SettingsDto;
import io.github.udanfernando.vestige.dto.SettingsUpdateDto;
import io.github.udanfernando.vestige.exception.SettingsSyncException;
import io.github.udanfernando.vestige.service.SettingsService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/settings")
@RequiredArgsConstructor
public class SettingsController {

    private final SettingsService settingsService;

    @GetMapping
    public ResponseEntity<SettingsDto> getSettings() {
        return ResponseEntity.ok(settingsService.getSettings());
    }

    @PutMapping
    public ResponseEntity<Void> updateSettings(@RequestBody SettingsUpdateDto dto) {
        settingsService.updateSettings(dto);
        return ResponseEntity.noContent().build();
    }

    @ExceptionHandler(SettingsSyncException.class)
    public ResponseEntity<Map<String, String>> handleSyncFailure(SettingsSyncException ex) {
        HttpStatusCode upstreamStatus = ex.getStatusCode();

        // Branch 1: The scraper-server was reachable but rejected our inputs (e.g., 400, 422 Unprocessable)
        if (upstreamStatus != null && upstreamStatus.is4xxClientError()) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(Map.of("error", "Invalid configuration value: " + ex.getMessage()));
        }

        // Branch 2: True connection failure / 5xx internal server error from the upstream daemon
        return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                .body(Map.of("error", ex.getMessage()));
    }
}