package io.github.udanfernando.vestige.repository;

import io.github.udanfernando.vestige.entity.Series;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;

public interface SeriesRepository extends JpaRepository<Series, Long> {
    Optional<Series> findByName(String name);
}
