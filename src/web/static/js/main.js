/**
 * SlideFinder - Main Application Entry Point
 * 
 * A modular frontend for searching Microsoft Build & Ignite slides
 * and building custom slide decks with AI assistance.
 * 
 * @module main
 * @version 2.0.0
 */

'use strict';

import { loadFavorites } from './components/favorites.js';
import { initDisclaimer } from './components/disclaimer.js';
import { initAnimatedLogo } from './components/animated-logo.js';
import { initDebugIndicator } from './components/debug-indicator.js';
import { setupEventListeners } from './events/listeners.js';
import { getById } from './utils/dom.js';

/**
 * Initializes the application.
 * Sets up state, event listeners, and initial UI.
 */
function initApp() {
    // Load persisted favorites from localStorage
    loadFavorites();
    
    // Set up all DOM event listeners
    setupEventListeners();
    
    // Initialize disclaimer footer
    initDisclaimer();
    
    // Initialize animated logo
    initAnimatedLogo();
    
    // Initialize debug indicator (shows if DEBUG mode is enabled)
    initDebugIndicator();
    
    // Focus search input on load
    getById('q')?.focus();
    
    console.log('[SlideFinder] Application initialized');
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}

// Export for potential external use or testing
export { initApp };
