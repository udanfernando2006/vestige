package io.github.udanfernando.vestige.controller;

import io.github.udanfernando.vestige.dto.AvailabilityDto;
import io.github.udanfernando.vestige.dto.SnapshotHistoryDto;
import io.github.udanfernando.vestige.service.AvailabilityService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.math.BigDecimal;
import java.util.List;

import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
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
    void getHistory_usesDefaultLimitOf50() throws Exception {
        when(availabilityService.getHistory(eq("9780316452465"), eq(50)))
                .thenReturn(List.of(SnapshotHistoryDto.builder()
                        .storeName("sarasavi").status("IN_STOCK")
                        .price(new BigDecimal("1500.00")).build()));

        mockMvc.perform(get("/api/availability/history/9780316452465"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].storeName").value("sarasavi"));
    }

    @Test
    void getHistory_respectsLimitParam() throws Exception {
        when(availabilityService.getHistory(eq("9780316452465"), eq(5))).thenReturn(List.of());

        mockMvc.perform(get("/api/availability/history/9780316452465").param("limit", "5"))
                .andExpect(status().isOk());
    }
}