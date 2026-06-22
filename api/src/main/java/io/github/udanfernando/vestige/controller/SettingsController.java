package io.github.udanfernando.vestige.controller;

import io.github.udanfernando.vestige.dto.SettingsDto;
import io.github.udanfernando.vestige.dto.SettingsUpdateDto;
import io.github.udanfernando.vestige.exception.SettingsSyncException;
import io.github.udanfernando.vestige.service.SettingsService;
import lombok.RequiredArgsConstructor;
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

    // Scoped here, not GlobalExceptionHandler — mirrors RunController's pattern
    // for scraper-server-specific failures. 502, not 500: this API is acting as
    // a gateway to an upstream service it depends on, which is the more precise status.
    @ExceptionHandler(SettingsSyncException.class)
    public ResponseEntity<Map<String, String>> handleSyncFailure(SettingsSyncException ex) {
        return ResponseEntity.status(502).body(Map.of("error", ex.getMessage()));
    }
}