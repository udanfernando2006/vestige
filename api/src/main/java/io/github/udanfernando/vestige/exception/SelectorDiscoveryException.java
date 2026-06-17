package io.github.udanfernando.vestige.exception;

import lombok.Getter;

@Getter
public class SelectorDiscoveryException extends RuntimeException {
    private final String output;

    public SelectorDiscoveryException(String message, String output) {
        super(message);
        this.output = output;
    }
}