package io.github.udanfernando.vestige.service;

import io.github.udanfernando.vestige.dto.*;
import io.github.udanfernando.vestige.entity.*;
import io.github.udanfernando.vestige.exception.ResourceNotFoundException;
import io.github.udanfernando.vestige.repository.*;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class SeriesService {

    private final SeriesRepository seriesRepo;
    private final BookRepository bookRepo;

    @Transactional(readOnly = true)
    public List<SeriesDto> getAll() {
        return seriesRepo.findAll().stream().map(this::toDto).toList();
    }

    @Transactional
    public SeriesDto create(SeriesCreateDto dto) {
        if (seriesRepo.existsByName(dto.getName())) {
            throw new DataIntegrityViolationException("Series already exists: " + dto.getName());
        }
        Series series = Series.builder()
                .name(dto.getName())
                .author(dto.getAuthor())
                .description(dto.getDescription())
                .build();
        return toDto(seriesRepo.save(series));
    }

    @Transactional
    public SeriesDto update(Long id, SeriesUpdateDto dto) {
        Series series = seriesRepo.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Series not found: " + id));

        if (dto.getName() != null) {
            if (dto.getName().isBlank()) {
                throw new IllegalArgumentException("Series name cannot be blank");
            }
            if (!series.getName().equals(dto.getName()) && seriesRepo.existsByName(dto.getName())) {
                throw new DataIntegrityViolationException("Series already exists: " + dto.getName());
            }
            series.setName(dto.getName());
        }
        if (dto.getAuthor() != null) {
            series.setAuthor(dto.getAuthor().isEmpty() ? null : dto.getAuthor());
        }
        if (dto.getDescription() != null) {
            series.setDescription(dto.getDescription().isEmpty() ? null : dto.getDescription());
        }
        return toDto(seriesRepo.save(series));
    }

    // Books become standalone (series_id = null) — they are never deleted.
    @Transactional
    public void delete(Long id) {
        Series series = seriesRepo.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Series not found: " + id));

        List<Book> books = bookRepo.findBySeriesId(id);
        for (Book b : books) {
            b.setSeries(null);
        }
        bookRepo.saveAll(books);
        seriesRepo.delete(series);
    }

    private SeriesDto toDto(Series s) {
        return SeriesDto.builder()
                .id(s.getId())
                .name(s.getName())
                .bookCount(s.getBooks() != null ? s.getBooks().size() : 0)
                .author(s.getAuthor())
                .description(s.getDescription())
                .build();
    }
}