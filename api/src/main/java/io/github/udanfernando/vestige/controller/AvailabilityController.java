package io.github.udanfernando.vestige.controller;

import io.github.udanfernando.vestige.dto.*;
import io.github.udanfernando.vestige.service.AvailabilityService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/availability")
@RequiredArgsConstructor
public class AvailabilityController {

    private final AvailabilityService availabilityService;

    @GetMapping
    public ResponseEntity<List<AvailabilityDto>> getCurrentStatus() {
        return ResponseEntity.ok(availabilityService.getCurrentStatus());
    }

    @GetMapping("/history/{isbn}")
    public ResponseEntity<List<SnapshotHistoryDto>> getHistory(
            @PathVariable String isbn,
            @RequestParam(defaultValue = "50") int limit) {
        return ResponseEntity.ok(availabilityService.getHistory(isbn, limit));
    }
}