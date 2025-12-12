/**
 * LocalStorage Utility Functions
 * Provides type-safe localStorage operations with error handling.
 * @module utils/storage
 */

'use strict';

/** Storage key constants */
export const STORAGE_KEYS = Object.freeze({
    FAVORITES: 'slidefinder_favorites',
    RECENT: 'slidefinder_recent',
    DISCLAIMER_DISMISSED: 'slidefinder_disclaimer_dismissed'
});

/**
 * Safely retrieves and parses JSON from localStorage.
 * @param {string} key - The storage key
 * @param {*} defaultValue - Default value if key doesn't exist or parsing fails
 * @returns {*} The parsed value or default
 */
export function getItem(key, defaultValue = null) {
    try {
        const item = localStorage.getItem(key);
        if (item === null) {
            return defaultValue;
        }
        return JSON.parse(item);
    } catch (error) {
        console.warn(`[Storage] Failed to parse item "${key}":`, error.message);
        return defaultValue;
    }
}

/**
 * Safely stores a value as JSON in localStorage.
 * @param {string} key - The storage key
 * @param {*} value - The value to store (will be JSON stringified)
 * @returns {boolean} True if successful, false otherwise
 */
export function setItem(key, value) {
    try {
        localStorage.setItem(key, JSON.stringify(value));
        return true;
    } catch (error) {
        console.error(`[Storage] Failed to store item "${key}":`, error.message);
        return false;
    }
}

/**
 * Removes an item from localStorage.
 * @param {string} key - The storage key to remove
 * @returns {boolean} True if successful, false otherwise
 */
export function removeItem(key) {
    try {
        localStorage.removeItem(key);
        return true;
    } catch (error) {
        console.error(`[Storage] Failed to remove item "${key}":`, error.message);
        return false;
    }
}

/**
 * Checks if a storage key exists.
 * @param {string} key - The storage key
 * @returns {boolean} True if the key exists
 */
export function hasItem(key) {
    return localStorage.getItem(key) !== null;
}

/**
 * Gets a string value from localStorage (no JSON parsing).
 * @param {string} key - The storage key
 * @param {string} defaultValue - Default value if key doesn't exist
 * @returns {string} The stored string or default
 */
export function getString(key, defaultValue = '') {
    try {
        const item = localStorage.getItem(key);
        return item !== null ? item : defaultValue;
    } catch (error) {
        console.warn(`[Storage] Failed to get string "${key}":`, error.message);
        return defaultValue;
    }
}

/**
 * Sets a string value in localStorage (no JSON stringifying).
 * @param {string} key - The storage key
 * @param {string} value - The string value to store
 * @returns {boolean} True if successful
 */
export function setString(key, value) {
    try {
        localStorage.setItem(key, String(value));
        return true;
    } catch (error) {
        console.error(`[Storage] Failed to set string "${key}":`, error.message);
        return false;
    }
}
