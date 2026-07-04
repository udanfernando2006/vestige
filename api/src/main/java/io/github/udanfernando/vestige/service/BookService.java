package io.github.udanfernando.vestige.service;

import io.github.udanfernando.vestige.dto.*;
import io.github.udanfernando.vestige.entity.*;
import io.github.udanfernando.vestige.exception.ResourceNotFoundException;
import io.github.udanfernando.vestige.repository.*;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class BookService {

    private final BookRepository bookRepo;
    private final SeriesRepository seriesRepo;
    private final TrackingPairRepository pairRepo;
    private final AvailabilitySnapshotRepository snapshotRepo;

    // GET /api/books — returns books grouped by series
    @Transactional(readOnly = true)
    public List<BookGroupDto> getAllGrouped() {
        List<Book> books = bookRepo.findAllByOrderByNameAsc();

        // Group books by series name (null series → "standalone" group)
        Map<String, List<BookDto>> grouped = books.stream()
                .collect(Collectors.groupingBy(
                        b -> b.getSeries() != null ? b.getSeries().getName() : "__standalone__",
                        LinkedHashMap::new,
                        Collectors.mapping(this::toDto, Collectors.toList())
                ));

        return grouped.entrySet().stream()
                .map(e -> BookGroupDto.builder()
                        .seriesName("__standalone__".equals(e.getKey()) ? null : e.getKey())
                        .books(e.getValue())
                        .build())
                .collect(Collectors.toList());
    }

    // POST /api/books
    @Transactional
    public BookDto create(BookCreateDto dto) {
        if (bookRepo.existsByIsbn(dto.getIsbn())) {
            throw new DataIntegrityViolationException("ISBN already exists: " + dto.getIsbn());
        }

        Series series = null;
        if (dto.getSeriesName() != null && !dto.getSeriesName().isBlank()) {
            series = seriesRepo.findByName(dto.getSeriesName())
                    .orElseGet(() -> seriesRepo.save(
                            Series.builder().name(dto.getSeriesName()).build()
                    ));
        }

        Book book = Book.builder()
                .name(dto.getName())
                .isbn(dto.getIsbn())
                .seriesEntry(dto.isSeriesEntry())
                .series(series)
                .author(dto.getAuthor())
                .description(dto.getDescription())
                .build();

        return toDto(bookRepo.save(book));
    }

    // DELETE /api/books/{id} — explicit cascade to avoid FK constraint errors
    @Transactional
    public void delete(Long id) {
        Book book = bookRepo.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Book not found: " + id));

        List<TrackingPair> pairs = pairRepo.findByBookId(id);
        for (TrackingPair pair : pairs) {
            snapshotRepo.deleteAllByPairId(pair.getId());
        }
        pairRepo.deleteAll(pairs);
        bookRepo.delete(book);
    }

    // PATCH /api/books/{id} — author/description only, "" = clear, null = no change
    @Transactional
    public BookDto update(Long id, BookUpdateDto dto) {
        Book book = bookRepo.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Book not found: " + id));

        if (dto.getAuthor() != null) {
            book.setAuthor(dto.getAuthor().isEmpty() ? null : dto.getAuthor());
        }
        if (dto.getDescription() != null) {
            book.setDescription(dto.getDescription().isEmpty() ? null : dto.getDescription());
        }
        return toDto(bookRepo.save(book));
    }

    // PATCH /api/books/series — bulk reassignment; always replaces current series
    @Transactional
    public List<BookDto> bulkAssignSeries(BulkSeriesAssignDto dto) {
        boolean hasExisting = dto.getSeriesId() != null;
        boolean hasNew = dto.getNewSeriesName() != null && !dto.getNewSeriesName().isBlank();

        if (hasExisting == hasNew) {
            throw new IllegalArgumentException(
                    "Provide exactly one of seriesId or newSeriesName");
        }

        Series target = hasExisting
                ? seriesRepo.findById(dto.getSeriesId())
                .orElseThrow(() -> new ResourceNotFoundException("Series not found: " + dto.getSeriesId()))
                : seriesRepo.findByName(dto.getNewSeriesName())
                .orElseGet(() -> seriesRepo.save(Series.builder().name(dto.getNewSeriesName()).build()));

        List<Book> books = bookRepo.findAllById(dto.getBookIds());
        if (books.size() != dto.getBookIds().size()) {
            throw new ResourceNotFoundException("One or more books not found");
        }

        for (Book b : books) {
            b.setSeries(target); // replaces whatever was there before, including null
        }
        bookRepo.saveAll(books);

        return books.stream().map(this::toDto).toList();
    }

    private BookDto toDto(Book b) {
        return BookDto.builder()
                .id(b.getId())
                .name(b.getName())
                .isbn(b.getIsbn())
                .seriesEntry(b.isSeriesEntry())
                .seriesId(b.getSeries() != null ? b.getSeries().getId() : null)
                .seriesName(b.getSeries() != null ? b.getSeries().getName() : null)
                .author(b.getAuthor())
                .description(b.getDescription())
                .build();
    }
}
