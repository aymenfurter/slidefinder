/**
 * Unit Tests for DOM Utilities
 * @module utils/dom.test
 */

import { describe, it, expect } from 'vitest';
import {
    escapeHtml,
    formatMarkdown,
    createElement,
    getById,
    toggleClass
} from '../utils/dom.js';

describe('escapeHtml', () => {
    it('should escape HTML special characters', () => {
        expect(escapeHtml('<script>alert("xss")</script>')).toBe(
            '&lt;script&gt;alert("xss")&lt;/script&gt;'
        );
    });

    it('should escape ampersands', () => {
        expect(escapeHtml('A & B')).toBe('A &amp; B');
    });

    it('should not escape quotes (safe in text content)', () => {
        // DOM-based escaping via textContent doesn't escape quotes
        // because they're only dangerous in attribute contexts
        expect(escapeHtml('"quoted"')).toBe('"quoted"');
    });

    it('should handle empty string', () => {
        expect(escapeHtml('')).toBe('');
    });

    it('should handle null', () => {
        expect(escapeHtml(null)).toBe('');
    });

    it('should handle undefined', () => {
        expect(escapeHtml(undefined)).toBe('');
    });

    it('should convert numbers to strings', () => {
        expect(escapeHtml(123)).toBe('123');
    });

    it('should handle strings with no special characters', () => {
        expect(escapeHtml('Hello World')).toBe('Hello World');
    });
});

describe('formatMarkdown', () => {
    it('should format bold text', () => {
        expect(formatMarkdown('**bold**')).toBe('<strong>bold</strong>');
    });

    it('should format italic text', () => {
        expect(formatMarkdown('*italic*')).toBe('<em>italic</em>');
    });

    it('should format inline code', () => {
        expect(formatMarkdown('`code`')).toBe('<code>code</code>');
    });

    it('should convert newlines to <br>', () => {
        expect(formatMarkdown('line1\nline2')).toBe('line1<br>line2');
    });

    it('should escape HTML before formatting', () => {
        expect(formatMarkdown('**<script>**')).toBe('<strong>&lt;script&gt;</strong>');
    });

    it('should handle empty string', () => {
        expect(formatMarkdown('')).toBe('');
    });

    it('should handle null', () => {
        expect(formatMarkdown(null)).toBe('');
    });

    it('should handle multiple formatting in same text', () => {
        const result = formatMarkdown('**bold** and *italic* and `code`');
        expect(result).toContain('<strong>bold</strong>');
        expect(result).toContain('<em>italic</em>');
        expect(result).toContain('<code>code</code>');
    });
});

describe('createElement', () => {
    it('should create element with tag name', () => {
        const el = createElement('div');
        expect(el.tagName).toBe('DIV');
    });

    it('should set className attribute', () => {
        const el = createElement('div', { className: 'test-class' });
        expect(el.className).toBe('test-class');
    });

    it('should set id attribute', () => {
        const el = createElement('div', { id: 'test-id' });
        expect(el.id).toBe('test-id');
    });

    it('should set data attributes', () => {
        const el = createElement('div', {
            dataset: { userId: '123', active: 'true' }
        });
        expect(el.dataset.userId).toBe('123');
        expect(el.dataset.active).toBe('true');
    });

    it('should set text content from string', () => {
        const el = createElement('span', {}, 'Hello');
        expect(el.textContent).toBe('Hello');
    });

    it('should append child element', () => {
        const child = document.createElement('span');
        child.textContent = 'child';
        const parent = createElement('div', {}, child);
        expect(parent.children.length).toBe(1);
        expect(parent.firstChild.textContent).toBe('child');
    });

    it('should append array of children', () => {
        const child1 = document.createElement('span');
        const child2 = document.createElement('span');
        const parent = createElement('div', {}, [child1, child2]);
        expect(parent.children.length).toBe(2);
    });
});

describe('getById', () => {
    it('should return element by ID', () => {
        const el = document.createElement('div');
        el.id = 'test-element';
        document.body.appendChild(el);
        
        expect(getById('test-element')).toBe(el);
    });

    it('should return null for non-existent ID', () => {
        expect(getById('does-not-exist')).toBeNull();
    });
});

describe('toggleClass', () => {
    it('should add class when condition is true', () => {
        const el = document.createElement('div');
        toggleClass(el, 'active', true);
        expect(el.classList.contains('active')).toBe(true);
    });

    it('should remove class when condition is false', () => {
        const el = document.createElement('div');
        el.classList.add('active');
        toggleClass(el, 'active', false);
        expect(el.classList.contains('active')).toBe(false);
    });

    it('should handle null element gracefully', () => {
        expect(() => toggleClass(null, 'active', true)).not.toThrow();
    });
});
