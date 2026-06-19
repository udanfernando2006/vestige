package io.github.udanfernando.vestige.repository;


import io.github.udanfernando.vestige.entity.Book;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import java.util.List;
import java.util.Optional;

public interface BookRepository extends JpaRepository<Book, Long> {

    Optional<Book> findByIsbn(String isbn);

    boolean existsByIsbn(String isbn);

    // Eager-load series to avoid N+1 on the grouped books endpoint
    @EntityGraph(attributePaths = {"series"})
    List<Book> findAllByOrderByNameAsc();
}
