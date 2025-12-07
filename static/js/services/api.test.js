/**
 * Unit Tests for API Service
 * @module services/api.test
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
    isSessionId,
    getThumbnailUrl,
    getDeckDownloadUrl
} from '../services/api.js';

describe('isSessionId', () => {
    it('should return true for valid session IDs', () => {
        expect(isSessionId('BRK108')).toBe(true);
        expect(isSessionId('KEY001')).toBe(true);
        expect(isSessionId('THR502')).toBe(true);
        expect(isSessionId('SESS123')).toBe(true);
    });

    it('should return true for lowercase session IDs', () => {
        expect(isSessionId('brk108')).toBe(true);
        expect(isSessionId('key001')).toBe(true);
    });

    it('should return false for regular search queries', () => {
        expect(isSessionId('azure container')).toBe(false);
        expect(isSessionId('kubernetes deployment')).toBe(false);
    });

    it('should return false for empty string', () => {
        expect(isSessionId('')).toBe(false);
    });

    it('should return false for null/undefined', () => {
        expect(isSessionId(null)).toBe(false);
        expect(isSessionId(undefined)).toBe(false);
    });

    it('should return false for numbers only', () => {
        expect(isSessionId('12345')).toBe(false);
    });

    it('should return false for letters only', () => {
        expect(isSessionId('ABCDEF')).toBe(false);
    });

    it('should handle whitespace', () => {
        expect(isSessionId(' BRK108 ')).toBe(true);
    });
});

describe('getThumbnailUrl', () => {
    it('should return correct thumbnail URL', () => {
        expect(getThumbnailUrl('BRK108', 5)).toBe('/thumbnails/BRK108_5.png');
    });

    it('should handle different session codes', () => {
        expect(getThumbnailUrl('KEY001', 1)).toBe('/thumbnails/KEY001_1.png');
        expect(getThumbnailUrl('THR502', 25)).toBe('/thumbnails/THR502_25.png');
    });
});

describe('getDeckDownloadUrl', () => {
    it('should return correct download URL', () => {
        expect(getDeckDownloadUrl('session-123')).toBe('/api/deck-builder/download/session-123');
    });
});
