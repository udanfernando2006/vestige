package io.github.udanfernando.vestige.entity;

import jakarta.persistence.*;
import lombok.*;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "books")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Book {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String name;

    @Column(nullable = false, unique = true)
    private String isbn;

    @Column(name = "is_series_entry", nullable = false)
    @Builder.Default
    private boolean seriesEntry = false;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "series_id")
    private Series series;

    @OneToMany(mappedBy = "book", cascade = CascadeType.ALL)
    @Builder.Default
    private List<TrackingPair> trackingPairs = new ArrayList<>();
}
