/**
 * Unit Tests for Toast Notifications
 * @module utils/toast.test
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { showToast, hideToast } from '../utils/toast.js';

describe('showToast', () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });

    afterEach(() => {
        vi.useRealTimers();
        // Clean up any toasts
        document.querySelectorAll('.toast-notification').forEach(el => el.remove());
    });

    it('should create a toast element', () => {
        showToast('Test message');
        const toast = document.querySelector('.toast-notification');
        expect(toast).not.toBeNull();
        expect(toast.textContent).toBe('Test message');
    });

    it('should add visible class after creation', () => {
        showToast('Test message');
        vi.advanceTimersByTime(20);
        const toast = document.querySelector('.toast-notification');
        expect(toast.classList.contains('visible')).toBe(true);
    });

    it('should remove toast after duration', () => {
        showToast('Test message');
        vi.advanceTimersByTime(3000); // Default duration + fade time
        const toast = document.querySelector('.toast-notification');
        expect(toast).toBeNull();
    });

    it('should replace existing toast', () => {
        showToast('First message');
        showToast('Second message');
        const toasts = document.querySelectorAll('.toast-notification');
        expect(toasts.length).toBe(1);
        expect(toasts[0].textContent).toBe('Second message');
    });

    it('should set accessibility attributes', () => {
        showToast('Accessible message');
        const toast = document.querySelector('.toast-notification');
        expect(toast.getAttribute('role')).toBe('status');
        expect(toast.getAttribute('aria-live')).toBe('polite');
    });
});

describe('hideToast', () => {
    it('should remove existing toast', () => {
        showToast('Test message');
        expect(document.querySelector('.toast-notification')).not.toBeNull();
        hideToast();
        expect(document.querySelector('.toast-notification')).toBeNull();
    });

    it('should not throw when no toast exists', () => {
        expect(() => hideToast()).not.toThrow();
    });
});
