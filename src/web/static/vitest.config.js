import { defineConfig } from 'vitest/config';

export default defineConfig({
    test: {
        // Use jsdom for DOM testing
        environment: 'jsdom',
        
        // Test file patterns
        include: ['js/**/*.test.js', 'js/**/*.spec.js'],
        
        // Setup files run before each test file
        setupFiles: ['./js/__tests__/setup.js'],
        
        // Coverage configuration
        coverage: {
            provider: 'v8',
            reporter: ['text', 'html', 'lcov'],
            include: ['js/**/*.js'],
            exclude: ['js/**/*.test.js', 'js/**/*.spec.js', 'js/__tests__/**']
        },
        
        // Global test timeout
        testTimeout: 10000,
        
        // Reporter configuration
        reporters: ['verbose']
    }
});
