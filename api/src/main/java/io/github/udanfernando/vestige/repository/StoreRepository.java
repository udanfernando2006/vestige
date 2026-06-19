package io.github.udanfernando.vestige.repository;

import io.github.udanfernando.vestige.entity.Store;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;

public interface StoreRepository extends JpaRepository<Store, Long> {
    Optional<Store> findByName(String name);
    boolean existsByName(String name);
}
