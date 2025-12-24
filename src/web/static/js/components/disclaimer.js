/**
 * Disclaimer Footer Component
 * @module components/disclaimer
 */

'use strict';

import { getById } from '../utils/dom.js';
import { getString, setString, removeItem, STORAGE_KEYS } from '../utils/storage.js';

/** About page URL for users who decline (to learn more before deciding) */
const ABOUT_PAGE_URL = '/about';

/**
 * Updates the visibility of disclaimer, overlay, and consent link based on consent state.
 * @param {boolean} hasConsent - Whether user has given consent
 * @param {HTMLElement} footer - The disclaimer footer element
 * @param {HTMLElement} consentLink - The manage consent link container
 * @param {HTMLElement} overlay - The blocking overlay element
 */
function updateConsentUI(hasConsent, footer, consentLink, overlay) {
    if (hasConsent) {
        footer?.classList.add('hidden');
        consentLink?.classList.remove('hidden');
        overlay?.classList.add('hidden');
        document.body.style.overflow = '';
    } else {
        footer?.classList.remove('hidden');
        consentLink?.classList.add('hidden');
        overlay?.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }
}

/**
 * Initializes the disclaimer footer.
 * Blocks UI until user accepts. Shows "Manage Consent" link after accepting.
 */
export function initDisclaimer() {
    const footer = getById('disclaimer-footer');
    const agreeBtn = getById('disclaimer-agree-btn');
    const declineBtn = getById('disclaimer-decline-btn');
    const consentLinkContainer = getById('consent-link-container');
    const manageConsentBtn = getById('manage-consent-btn');
    const overlay = getById('gdpr-overlay');
    
    if (!footer) return;
    
    // Check if already agreed
    const hasConsent = getString(STORAGE_KEYS.DISCLAIMER_DISMISSED, '') === 'true';
    
    // Show/hide based on consent state (blocks UI if no consent)
    updateConsentUI(hasConsent, footer, consentLinkContainer, overlay);
    
    // Handle agree button click
    if (agreeBtn) {
        agreeBtn.addEventListener('click', () => {
            setString(STORAGE_KEYS.DISCLAIMER_DISMISSED, 'true');
            updateConsentUI(true, footer, consentLinkContainer, overlay);
        });
    }
    
    // Handle decline button click - redirect to about page
    if (declineBtn) {
        declineBtn.addEventListener('click', () => {
            removeItem(STORAGE_KEYS.DISCLAIMER_DISMISSED);
            window.location.href = ABOUT_PAGE_URL;
        });
    }
    
    // Handle manage consent / withdraw consent - show the popup again
    if (manageConsentBtn) {
        manageConsentBtn.addEventListener('click', () => {
            // Show the disclaimer popup again (with overlay)
            updateConsentUI(false, footer, consentLinkContainer, overlay);
        });
    }
}
