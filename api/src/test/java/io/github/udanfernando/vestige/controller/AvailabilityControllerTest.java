package io.github.udanfernando.vestige.controller;

import io.github.udanfernando.vestige.dto.AvailabilityDto;
import io.github.udanfernando.vestige.dto.SnapshotHistoryDto;
import io.github.udanfernando.vestige.exception.ResourceNotFoundException;
import io.github.udanfernando.vestige.service.AvailabilityService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.math.BigDecimal;
import java.util.List;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(AvailabilityController.class)
class AvailabilityControllerTest {

    @Autowired private MockMvc mockMvc;

    @MockitoBean
    private AvailabilityService availabilityService;

    @Test
    void getCurrentStatus_returnsLatestSnapshots() throws Exception {
        AvailabilityDto dto = AvailabilityDto.builder()
                .pairId(1L).bookName("The Last Wish").storeName("sarasavi")
                .status("IN_STOCK").price(new BigDecimal("1500.00"))
                .build();

        when(availabilityService.getCurrentStatus()).thenReturn(List.of(dto));

        mockMvc.perform(get("/api/availability"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].status").value("IN_STOCK"))
                .andExpect(jsonPath("$[0].price").value(1500.00));
    }

    @Test
    void getHistory_withNoFilters_usesDefaultLimitOf100() throws Exception {
        when(availabilityService.getHistory(isNull(), isNull(), isNull(), eq(100)))
                .thenReturn(List.of(SnapshotHistoryDto.builder()
                        .id(1L).pairId(1L).bookName("The Last Wish")
                        .storeName("sarasavi").status("IN_STOCK")
                        .price(new BigDecimal("1500.00")).build()));

        mockMvc.perform(get("/api/availability/history"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].bookName").value("The Last Wish"));
    }

    @Test
    void getHistory_filtersByIsbnStoreAndStatus() throws Exception {
        when(availabilityService.getHistory(eq("9780316452465"), eq("sarasavi"), eq("IN_STOCK"), eq(5)))
                .thenReturn(List.of());

        mockMvc.perform(get("/api/availability/history")
                        .param("isbn", "9780316452465")
                        .param("storeName", "sarasavi")
                        .param("status", "IN_STOCK")
                        .param("limit", "5"))
                .andExpect(status().isOk());
    }

    @Test
    void deleteSnapshot_returns204() throws Exception {
        mockMvc.perform(delete("/api/availability/7"))
                .andExpect(status().isNoContent());
        verify(availabilityService).deleteSnapshot(7L);
    }

    @Test
    void deleteSnapshot_unknownId_returns404() throws Exception {
        doThrow(new ResourceNotFoundException("Snapshot not found: 99"))
                .when(availabilityService).deleteSnapshot(99L);

        mockMvc.perform(delete("/api/availability/99"))
                .andExpect(status().isNotFound());
    }

    @Test
    void deleteHistoryForPair_returns204() throws Exception {
        mockMvc.perform(delete("/api/availability/pair/3"))
                .andExpect(status().isNoContent());
        verify(availabilityService).deleteHistoryForPair(3L);
    }

    @Test
    void deleteHistoryForPair_unknownPairId_returns404() throws Exception {
        doThrow(new ResourceNotFoundException("Tracking pair not found: 99"))
                .when(availabilityService).deleteHistoryForPair(99L);

        mockMvc.perform(delete("/api/availability/pair/99"))
                .andExpect(status().isNotFound());
    }
}