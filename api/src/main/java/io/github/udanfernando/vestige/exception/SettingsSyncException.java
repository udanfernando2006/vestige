package io.github.udanfernando.vestige.exception;

import lombok.Getter;
import org.springframework.http.HttpStatusCode;

@Getter
public class SettingsSyncException extends RuntimeException {

    private final HttpStatusCode statusCode;

    public SettingsSyncException(String message) {
        super(message);
        this.statusCode = null;
    }

    public SettingsSyncException(String message, HttpStatusCode statusCode) {
        super(message);
        this.statusCode = statusCode;
    }
}