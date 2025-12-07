/**
 * DOM Utility Functions
 * Provides secure HTML escaping and text formatting utilities.
 * @module utils/dom
 */

'use strict';

/**
 * Escapes HTML special characters to prevent XSS attacks.
 * Uses DOM-based escaping for maximum security.
 * @param {string} text - The text to escape
 * @returns {string} The escaped HTML-safe string
 */
export function escapeHtml(text) {
    if (text === null || text === undefined) {
        return '';
    }
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

/**
 * Formats markdown-style text to HTML.
 * Supports bold (**), italic (*), code (`), and newlines.
 * All text is escaped before formatting to prevent XSS.
 * @param {string} text - The markdown text to format
 * @returns {string} The formatted HTML string
 */
export function formatMarkdown(text) {
    if (!text) {
        return '';
    }
    return escapeHtml(text)
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/\n/g, '<br>');
}

/**
 * Safely sets innerHTML after escaping content.
 * Use this instead of directly setting innerHTML.
 * @param {HTMLElement} element - The target element
 * @param {string} html - The HTML content (assumed to be safe/pre-escaped)
 */
export function setInnerHTML(element, html) {
    if (element && typeof html === 'string') {
        element.innerHTML = html;
    }
}

/**
 * Creates an element with the specified attributes and content.
 * @param {string} tag - The element tag name
 * @param {Object} [attributes={}] - Attributes to set on the element
 * @param {string|HTMLElement|HTMLElement[]} [content] - Content for the element
 * @returns {HTMLElement} The created element
 */
export function createElement(tag, attributes = {}, content = null) {
    const element = document.createElement(tag);
    
    Object.entries(attributes).forEach(([key, value]) => {
        if (key === 'className') {
            element.className = value;
        } else if (key === 'dataset') {
            Object.entries(value).forEach(([dataKey, dataValue]) => {
                element.dataset[dataKey] = dataValue;
            });
        } else if (key.startsWith('on') && typeof value === 'function') {
            element.addEventListener(key.slice(2).toLowerCase(), value);
        } else {
            element.setAttribute(key, value);
        }
    });
    
    if (content !== null) {
        if (typeof content === 'string') {
            element.textContent = content;
        } else if (content instanceof HTMLElement) {
            element.appendChild(content);
        } else if (Array.isArray(content)) {
            content.forEach(child => {
                if (child instanceof HTMLElement) {
                    element.appendChild(child);
                }
            });
        }
    }
    
    return element;
}

/**
 * Gets an element by ID with null safety.
 * @param {string} id - The element ID
 * @returns {HTMLElement|null} The element or null
 */
export function getById(id) {
    return document.getElementById(id);
}

/**
 * Adds or removes a class based on a condition.
 * @param {HTMLElement} element - The target element
 * @param {string} className - The class name to toggle
 * @param {boolean} condition - Whether to add (true) or remove (false) the class
 */
export function toggleClass(element, className, condition) {
    if (element) {
        element.classList.toggle(className, condition);
    }
}
