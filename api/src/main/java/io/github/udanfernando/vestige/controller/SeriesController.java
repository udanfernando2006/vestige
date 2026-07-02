package io.github.udanfernando.vestige.controller;

import io.github.udanfernando.vestige.dto.*;
import io.github.udanfernando.vestige.service.SeriesService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/series")
@RequiredArgsConstructor
public class SeriesController {

    private final SeriesService seriesService;

    @GetMapping
    public ResponseEntity<List<SeriesDto>> getAll() {
        return ResponseEntity.ok(seriesService.getAll());
    }

    @PostMapping
    public ResponseEntity<SeriesDto> create(@Valid @RequestBody SeriesCreateDto dto) {
        return ResponseEntity.status(201).body(seriesService.create(dto));
    }

    @PatchMapping("/{id}")
    public ResponseEntity<SeriesDto> update(@PathVariable Long id, @RequestBody SeriesUpdateDto dto) {
        return ResponseEntity.ok(seriesService.update(id, dto));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {
        seriesService.delete(id);
        return ResponseEntity.noContent().build();
    }
}