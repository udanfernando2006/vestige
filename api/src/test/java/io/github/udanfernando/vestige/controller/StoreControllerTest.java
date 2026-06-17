package io.github.udanfernando.vestige.controller;

import tools.jackson.databind.ObjectMapper;
import io.github.udanfernando.vestige.dto.StoreCreateDto;
import io.github.udanfernando.vestige.dto.StoreDto;
import io.github.udanfernando.vestige.service.StoreService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(StoreController.class)
class StoreControllerTest {

    @Autowired private MockMvc mockMvc;
    @Autowired private ObjectMapper objectMapper;

    @MockitoBean
    private StoreService storeService;

    @Test
    void getAll_returnsStores() throws Exception {
        StoreDto store = StoreDto.builder().id(1L).name("sarasavi").baseUrl("https://sarasavi.lk").build();
        when(storeService.getAll()).thenReturn(List.of(store));

        mockMvc.perform(get("/api/stores"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].name").value("sarasavi"))
                .andExpect(jsonPath("$[0].baseUrl").value("https://sarasavi.lk"));
    }

    @Test
    void create_returnsCreatedStore() throws Exception {
        StoreCreateDto dto = StoreCreateDto.builder().name("bookshop_lk").baseUrl("https://bookshop.lk").build();
        StoreDto created = StoreDto.builder().id(3L).name("bookshop_lk").baseUrl("https://bookshop.lk").build();

        when(storeService.create(any())).thenReturn(created);

        mockMvc.perform(post("/api/stores")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(dto)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").value(3))
                .andExpect(jsonPath("$.name").value("bookshop_lk"));
    }

    @Test
    void create_missingName_returns400() throws Exception {
        StoreCreateDto invalid = StoreCreateDto.builder().baseUrl("https://x.lk").build();

        mockMvc.perform(post("/api/stores")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(invalid)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.name").exists());
    }

    @Test
    void create_duplicateName_returns409() throws Exception {
        StoreCreateDto dto = StoreCreateDto.builder().name("sarasavi").baseUrl("https://sarasavi.lk").build();

        when(storeService.create(any()))
                .thenThrow(new DataIntegrityViolationException("Store name already exists"));

        mockMvc.perform(post("/api/stores")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(dto)))
                .andExpect(status().isConflict());
    }
}