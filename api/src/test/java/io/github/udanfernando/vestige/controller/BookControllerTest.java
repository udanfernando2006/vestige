package io.github.udanfernando.vestige.controller;

import tools.jackson.databind.ObjectMapper;
import io.github.udanfernando.vestige.dto.BookCreateDto;
import io.github.udanfernando.vestige.dto.BookDto;
import io.github.udanfernando.vestige.dto.BookGroupDto;
import io.github.udanfernando.vestige.service.BookService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
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
}
