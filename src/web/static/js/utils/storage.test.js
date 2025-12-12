/**
 * Unit Tests for Storage Utilities
 * @module utils/storage.test
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
    getItem,
    setItem,
    removeItem,
    hasItem,
    getString,
    setString,
    STORAGE_KEYS
} from '../utils/storage.js';

describe('STORAGE_KEYS', () => {
    it('should be frozen', () => {
        expect(Object.isFrozen(STORAGE_KEYS)).toBe(true);
    });

    it('should have expected keys', () => {
        expect(STORAGE_KEYS.FAVORITES).toBe('slidefinder_favorites');
        expect(STORAGE_KEYS.RECENT).toBe('slidefinder_recent');
        expect(STORAGE_KEYS.DISCLAIMER_DISMISSED).toBe('slidefinder_disclaimer_dismissed');
    });
});

describe('getItem', () => {
    it('should parse JSON from localStorage', () => {
        localStorage.setItem('test', JSON.stringify({ foo: 'bar' }));
        expect(getItem('test')).toEqual({ foo: 'bar' });
    });

    it('should return default value when key does not exist', () => {
        expect(getItem('nonexistent', 'default')).toBe('default');
    });

    it('should return null as default when no default provided', () => {
        expect(getItem('nonexistent')).toBeNull();
    });

    it('should return default value on parse error', () => {
        localStorage.setItem('invalid', 'not-json');
        expect(getItem('invalid', [])).toEqual([]);
    });

    it('should handle arrays', () => {
        localStorage.setItem('array', JSON.stringify([1, 2, 3]));
        expect(getItem('array')).toEqual([1, 2, 3]);
    });
});

describe('setItem', () => {
    it('should store JSON in localStorage', () => {
        setItem('test', { foo: 'bar' });
        expect(JSON.parse(localStorage.getItem('test'))).toEqual({ foo: 'bar' });
    });

    it('should return true on success', () => {
        expect(setItem('test', 'value')).toBe(true);
    });

    it('should store arrays', () => {
        setItem('arr', [1, 2, 3]);
        expect(JSON.parse(localStorage.getItem('arr'))).toEqual([1, 2, 3]);
    });

    it('should store primitives', () => {
        setItem('num', 42);
        expect(getItem('num')).toBe(42);
    });
});

describe('removeItem', () => {
    it('should remove item from localStorage', () => {
        localStorage.setItem('test', 'value');
        removeItem('test');
        expect(localStorage.getItem('test')).toBeNull();
    });

    it('should return true on success', () => {
        expect(removeItem('test')).toBe(true);
    });

    it('should not throw for non-existent key', () => {
        expect(() => removeItem('nonexistent')).not.toThrow();
    });
});

describe('hasItem', () => {
    it('should return true when key exists', () => {
        localStorage.setItem('exists', 'value');
        expect(hasItem('exists')).toBe(true);
    });

    it('should return false when key does not exist', () => {
        expect(hasItem('does-not-exist')).toBe(false);
    });
});

describe('getString', () => {
    it('should return raw string from localStorage', () => {
        localStorage.setItem('str', 'hello');
        expect(getString('str')).toBe('hello');
    });

    it('should return default value when key does not exist', () => {
        expect(getString('nonexistent', 'default')).toBe('default');
    });

    it('should return empty string as default', () => {
        expect(getString('nonexistent')).toBe('');
    });
});

describe('setString', () => {
    it('should store string in localStorage', () => {
        setString('str', 'hello');
        expect(localStorage.getItem('str')).toBe('hello');
    });

    it('should return true on success', () => {
        expect(setString('str', 'value')).toBe(true);
    });

    it('should convert non-strings to strings', () => {
        setString('num', 42);
        expect(localStorage.getItem('num')).toBe('42');
    });
});
