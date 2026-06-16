package io.github.udanfernando.vestige.controller;

import io.github.udanfernando.vestige.dto.*;
import io.github.udanfernando.vestige.service.StoreService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/stores")
@RequiredArgsConstructor
public class StoreController {

    private final StoreService storeService;

    @GetMapping
    public ResponseEntity<List<StoreDto>> getAll() {
        return ResponseEntity.ok(storeService.getAll());
    }

    @PostMapping
    public ResponseEntity<StoreDto> create(@Valid @RequestBody StoreCreateDto dto) {
        return ResponseEntity.status(201).body(storeService.create(dto));
    }
}