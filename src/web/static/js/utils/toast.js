/**
 * Toast Notification Component
 * Provides non-blocking user feedback notifications.
 * @module utils/toast
 */

'use strict';

/** Toast display duration in milliseconds */
const TOAST_DURATION = 2500;

/** Toast fade-out transition time in milliseconds */
const TOAST_FADE_TIME = 300;

/** CSS class for the toast element */
const TOAST_CLASS = 'toast-notification';

/** CSS class when toast is visible */
const TOAST_VISIBLE_CLASS = 'visible';

/**
 * Shows a toast notification message.
 * Only one toast is shown at a time - new toasts replace existing ones.
 * @param {string} message - The message to display
 * @param {Object} [options={}] - Optional configuration
 * @param {number} [options.duration=2500] - Display duration in ms
 */
export function showToast(message, options = {}) {
    const { duration = TOAST_DURATION } = options;
    
    // Remove any existing toast
    const existingToast = document.querySelector(`.${TOAST_CLASS}`);
    if (existingToast) {
        existingToast.remove();
    }
    
    // Create new toast element
    const toast = document.createElement('div');
    toast.className = TOAST_CLASS;
    toast.textContent = message;
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');
    
    document.body.appendChild(toast);
    
    // Trigger reflow to enable CSS transition
    // Using void to indicate intentional no-op
    void toast.offsetWidth;
    
    // Show toast
    toast.classList.add(TOAST_VISIBLE_CLASS);
    
    // Hide and remove toast after duration
    setTimeout(() => {
        toast.classList.remove(TOAST_VISIBLE_CLASS);
        setTimeout(() => {
            if (toast.parentNode) {
                toast.remove();
            }
        }, TOAST_FADE_TIME);
    }, duration);
}

/**
 * Removes any currently visible toast immediately.
 */
export function hideToast() {
    const toast = document.querySelector(`.${TOAST_CLASS}`);
    if (toast) {
        toast.remove();
    }
}
