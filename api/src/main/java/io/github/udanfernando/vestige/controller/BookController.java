package io.github.udanfernando.vestige.controller;

import io.github.udanfernando.vestige.dto.*;
import io.github.udanfernando.vestige.service.BookService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/books")
@RequiredArgsConstructor
public class BookController {

    private final BookService bookService;

    @GetMapping
    public ResponseEntity<List<BookGroupDto>> getAll() {
        return ResponseEntity.ok(bookService.getAllGrouped());
    }

    @PostMapping
    public ResponseEntity<BookDto> create(@Valid @RequestBody BookCreateDto dto) {
        return ResponseEntity.status(201).body(bookService.create(dto));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {
        bookService.delete(id);
        return ResponseEntity.noContent().build();
    }

    @PatchMapping("/{id}")
    public ResponseEntity<BookDto> update(@PathVariable Long id, @RequestBody BookUpdateDto dto) {
        return ResponseEntity.ok(bookService.update(id, dto));
    }

    @PatchMapping("/series")
    public ResponseEntity<List<BookDto>> bulkAssignSeries(@Valid @RequestBody BulkSeriesAssignDto dto) {
        return ResponseEntity.ok(bookService.bulkAssignSeries(dto));
    }
}