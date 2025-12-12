/**
 * Disclaimer Footer Component
 * Handles the dismissible disclaimer footer.
 * @module components/disclaimer
 */

'use strict';

import { getById } from '../utils/dom.js';
import { getString, setString, STORAGE_KEYS } from '../utils/storage.js';

/**
 * Initializes the disclaimer footer.
 * Hides if previously dismissed.
 */
export function initDisclaimer() {
    const footer = getById('disclaimer-footer');
    const dismissBtn = getById('disclaimer-dismiss-btn');
    
    if (!footer) return;
    
    // Check if already dismissed
    if (getString(STORAGE_KEYS.DISCLAIMER_DISMISSED, '') === 'true') {
        footer.classList.add('hidden');
        return;
    }
    
    // Handle dismiss button click
    if (dismissBtn) {
        dismissBtn.addEventListener('click', () => {
            footer.classList.add('hidden');
            setString(STORAGE_KEYS.DISCLAIMER_DISMISSED, 'true');
        });
    }
}
