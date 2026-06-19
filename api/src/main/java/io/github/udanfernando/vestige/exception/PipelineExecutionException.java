package io.github.udanfernando.vestige.exception;

import lombok.Getter;

@Getter
public class PipelineExecutionException extends RuntimeException {
    private final String output;

    public PipelineExecutionException(String message, String output) {
        super(message);
        this.output = output;
    }
}