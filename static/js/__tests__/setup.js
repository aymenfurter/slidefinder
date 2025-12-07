/**
 * Test Setup File
 * Runs before each test file to configure the test environment.
 */

import { beforeEach, afterEach, vi } from 'vitest';

// Reset DOM before each test
beforeEach(() => {
    document.body.innerHTML = '';
    document.head.innerHTML = '';
});

// Clear all mocks after each test
afterEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
});

// Mock localStorage
const localStorageMock = (() => {
    let store = {};
    return {
        getItem: vi.fn((key) => store[key] || null),
        setItem: vi.fn((key, value) => {
            store[key] = String(value);
        }),
        removeItem: vi.fn((key) => {
            delete store[key];
        }),
        clear: vi.fn(() => {
            store = {};
        }),
        get length() {
            return Object.keys(store).length;
        },
        key: vi.fn((index) => Object.keys(store)[index] || null)
    };
})();

Object.defineProperty(window, 'localStorage', {
    value: localStorageMock,
    writable: true
});

// Reset localStorage mock before each test
beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
});

// Mock fetch globally
global.fetch = vi.fn();

// Mock console methods to reduce noise (optional - comment out for debugging)
// vi.spyOn(console, 'log').mockImplementation(() => {});
// vi.spyOn(console, 'warn').mockImplementation(() => {});
