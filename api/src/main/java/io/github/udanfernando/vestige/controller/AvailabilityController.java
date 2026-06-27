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

    // Replaces GET /api/availability/history/{isbn}. Every filter is an optional
    // query param now, so this one endpoint covers "everything," "one book," "one
    // store," "one status," or any combination.
    @GetMapping("/history")
    public ResponseEntity<List<SnapshotHistoryDto>> getHistory(
            @RequestParam(required = false) String isbn,
            @RequestParam(required = false) String storeName,
            @RequestParam(required = false) String status,
            @RequestParam(defaultValue = "100") int limit) {
        return ResponseEntity.ok(availabilityService.getHistory(isbn, storeName, status, limit));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteSnapshot(@PathVariable Long id) {
        availabilityService.deleteSnapshot(id);
        return ResponseEntity.noContent().build();
    }

    @DeleteMapping("/pair/{pairId}")
    public ResponseEntity<Void> deleteHistoryForPair(@PathVariable Long pairId) {
        availabilityService.deleteHistoryForPair(pairId);
        return ResponseEntity.noContent().build();
    }
}