package io.github.udanfernando.vestige.entity;

import jakarta.persistence.*;
import lombok.*;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
@Table(name = "availability_snapshots")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class AvailabilitySnapshot {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "pair_id", nullable = false)
    private TrackingPair pair;

    @Column(name = "in_stock")
    private Boolean inStock;

    @Column(precision = 10, scale = 2)
    private BigDecimal price;

    @Column(nullable = false)
    private String status;

    // "scraper" or "llm_direct" — which pipeline path produced this row
    private String source;

    @Column(name = "scraped_at", nullable = false)
    private LocalDateTime scrapedAt;
}
