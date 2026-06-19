package io.github.udanfernando.vestige.entity;

import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(
        name = "tracking_pairs",
        uniqueConstraints = @UniqueConstraint(columnNames = {"book_id", "store_id"})
)
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class TrackingPair {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "book_id", nullable = false)
    private Book book;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "store_id", nullable = false)
    private Store store;

    @Column(name = "product_url")
    private String productUrl;

    @Column(name = "price_selector")
    private String priceSelector;

    @Column(name = "stock_selector")
    private String stockSelector;

    @Column(nullable = false)
    @Builder.Default
    private String status = "PENDING";

    @Column(name = "selector_found_at")
    private LocalDateTime selectorFoundAt;

    @OneToMany(mappedBy = "pair", cascade = CascadeType.ALL)
    @Builder.Default
    private List<AvailabilitySnapshot> snapshots = new ArrayList<>();
}
