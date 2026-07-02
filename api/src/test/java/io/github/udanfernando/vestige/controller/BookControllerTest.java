package io.github.udanfernando.vestige.controller;

import io.github.udanfernando.vestige.dto.*;
import tools.jackson.databind.ObjectMapper;

import io.github.udanfernando.vestige.service.BookService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(BookController.class)
class BookControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockitoBean                              // @MockBean is removed in Spring Boot 4.x
    private BookService bookService;

    @Test
    void getAll_returnsGroupedBooks() throws Exception {
        BookDto bookDto = BookDto.builder()
                .id(1L).name("The Last Wish").isbn("9780316452465").build();

        BookGroupDto group = BookGroupDto.builder()
                .seriesName("The Witcher")
                .books(List.of(bookDto))
                .build();

        when(bookService.getAllGrouped()).thenReturn(List.of(group));

        mockMvc.perform(get("/api/books"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].seriesName").value("The Witcher"))
                .andExpect(jsonPath("$[0].books[0].name").value("The Last Wish"));
    }

    @Test
    void create_returnsCreatedBook() throws Exception {
        BookCreateDto createDto = BookCreateDto.builder()
                .name("Blood of Elves")
                .isbn("9780316029193")
                .seriesName("The Witcher")
                .build();

        BookDto created = BookDto.builder()
                .id(4L).name("Blood of Elves").isbn("9780316029193").build();

        when(bookService.create(any())).thenReturn(created);

        mockMvc.perform(post("/api/books")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(createDto)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").value(4))
                .andExpect(jsonPath("$.name").value("Blood of Elves"));
    }

    @Test
    void create_missingIsbn_returns400() throws Exception {
        BookCreateDto invalid = BookCreateDto.builder().name("No ISBN").build();

        mockMvc.perform(post("/api/books")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(invalid)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.isbn").exists());
    }

    @Test
    void update_returnsUpdatedBook() throws Exception {
        BookUpdateDto updateDto = BookUpdateDto.builder().author("New Author").build();
        BookDto updated = BookDto.builder()
                .id(1L).name("The Last Wish").isbn("9780316452465").author("New Author").build();

        when(bookService.update(eq(1L), any())).thenReturn(updated);

        mockMvc.perform(patch("/api/books/1")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(updateDto)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.author").value("New Author"));
    }

    @Test
    void bulkAssignSeries_returnsUpdatedBooks() throws Exception {
        BulkSeriesAssignDto bulkDto = BulkSeriesAssignDto.builder()
                .bookIds(List.of(1L, 2L)).newSeriesName("The Witcher").build();

        BookDto book1 = BookDto.builder().id(1L).name("The Last Wish").isbn("A").seriesName("The Witcher").build();
        BookDto book2 = BookDto.builder().id(2L).name("Sword of Destiny").isbn("B").seriesName("The Witcher").build();

        when(bookService.bulkAssignSeries(any())).thenReturn(List.of(book1, book2));

        mockMvc.perform(patch("/api/books/series")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(bulkDto)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].seriesName").value("The Witcher"))
                .andExpect(jsonPath("$[1].seriesName").value("The Witcher"));
    }
}
