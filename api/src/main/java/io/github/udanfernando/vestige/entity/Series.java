package io.github.udanfernando.vestige.entity;

import jakarta.persistence.*;
import lombok.*;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "series")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Series {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true)
    private String name;

    @OneToMany(mappedBy = "series")
    @Builder.Default
    private List<Book> books = new ArrayList<>();

    @Column(columnDefinition = "TEXT")
    private String author;

    @Column(columnDefinition = "TEXT")
    private String description;
}
