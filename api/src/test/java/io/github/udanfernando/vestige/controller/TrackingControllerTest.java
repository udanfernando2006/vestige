package io.github.udanfernando.vestige.controller;

import tools.jackson.databind.ObjectMapper;
import io.github.udanfernando.vestige.dto.*;
import io.github.udanfernando.vestige.exception.ResourceNotFoundException;
import io.github.udanfernando.vestige.service.TrackingService;
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

@WebMvcTest(TrackingController.class)
class TrackingControllerTest {

    @Autowired private MockMvc mockMvc;
    @Autowired private ObjectMapper objectMapper;

    @MockitoBean
    private TrackingService trackingService;

    private TrackingPairDto samplePair(Long id, String status) {
        BookDto book = BookDto.builder().id(1L).name("The Last Wish").isbn("9780316452465").build();
        StoreDto store = StoreDto.builder().id(1L).name("sarasavi").build();
        return TrackingPairDto.builder()
                .id(id).book(book).store(store)
                .productUrl("https://sarasavi.lk/books/last-wish")
                .selectorsCached(false)
                .status(status)
                .build();
    }

    @Test
    void getAll_returnsPairs() throws Exception {
        when(trackingService.getAll()).thenReturn(List.of(samplePair(1L, "PENDING")));

        mockMvc.perform(get("/api/tracking"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].status").value("PENDING"))
                .andExpect(jsonPath("$[0].book.isbn").value("9780316452465"));
    }

    // Regression test for the path-matching gotcha in Part 13:
    // /needs-setup must not be swallowed by {id}
    @Test
    void getNeedsSetup_resolvesToDedicatedEndpoint() throws Exception {
        when(trackingService.getNeedsSetup()).thenReturn(List.of(samplePair(3L, "NEEDS_SETUP")));

        mockMvc.perform(get("/api/tracking/needs-setup"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].status").value("NEEDS_SETUP"));
    }

    @Test
    void create_returnsCreatedPair() throws Exception {
        TrackingPairCreateDto dto = TrackingPairCreateDto.builder()
                .isbn("9780316452465").storeName("vijitha_yapa").build();

        when(trackingService.create(any())).thenReturn(samplePair(5L, "PENDING"));

        mockMvc.perform(post("/api/tracking")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(dto)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").value(5));
    }

    @Test
    void create_unknownIsbn_returns404() throws Exception {
        TrackingPairCreateDto dto = TrackingPairCreateDto.builder()
                .isbn("0000000000000").storeName("sarasavi").build();

        when(trackingService.create(any()))
                .thenThrow(new ResourceNotFoundException("Book not found with ISBN: 0000000000000"));

        mockMvc.perform(post("/api/tracking")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(dto)))
                .andExpect(status().isNotFound());
    }

    @Test
    void update_withBothSelectors_transitionsToPending() throws Exception {
        TrackingPairUpdateDto dto = TrackingPairUpdateDto.builder()
                .priceSelector("div[class*='price'] span")
                .stockSelector("div[class*='stock'] span")
                .build();

        TrackingPairDto updated = samplePair(3L, "PENDING");
        updated.setSelectorsCached(true);

        when(trackingService.update(eq(3L), any())).thenReturn(updated);

        mockMvc.perform(patch("/api/tracking/3")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(dto)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("PENDING"))
                .andExpect(jsonPath("$.selectorsCached").value(true));
    }

    @Test
    void update_unknownId_returns404() throws Exception {
        TrackingPairUpdateDto dto = TrackingPairUpdateDto.builder().status("SKIP").build();

        when(trackingService.update(eq(99L), any()))
                .thenThrow(new ResourceNotFoundException("Tracking pair not found: 99"));

        mockMvc.perform(patch("/api/tracking/99")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(dto)))
                .andExpect(status().isNotFound());
    }
}