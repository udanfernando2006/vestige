package io.github.udanfernando.vestige.controller;

import io.github.udanfernando.vestige.dto.*;
import io.github.udanfernando.vestige.service.TrackingService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/tracking")
@RequiredArgsConstructor
public class TrackingController {

    private final TrackingService trackingService;

    @GetMapping
    public ResponseEntity<List<TrackingPairDto>> getAll() {
        return ResponseEntity.ok(trackingService.getAll());
    }

    // Must be declared before /{id} or Spring matches "needs-setup" as a path variable
    @GetMapping("/needs-setup")
    public ResponseEntity<List<TrackingPairDto>> getNeedsSetup() {
        return ResponseEntity.ok(trackingService.getNeedsSetup());
    }

    @PostMapping
    public ResponseEntity<TrackingPairDto> create(@Valid @RequestBody TrackingPairCreateDto dto) {
        return ResponseEntity.status(201).body(trackingService.create(dto));
    }

    @PatchMapping("/{id}")
    public ResponseEntity<TrackingPairDto> update(
            @PathVariable Long id,
            @RequestBody TrackingPairUpdateDto dto) {
        return ResponseEntity.ok(trackingService.update(id, dto));
    }
}