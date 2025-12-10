/**
 * Event Listeners Module
 * Sets up all DOM event listeners.
 * @module events/listeners
 */

'use strict';

import { getById } from '../utils/dom.js';
import { get } from '../state/store.js';

import {
    search,
    enterSearchMode,
    exitSearchMode,
    toggleFilter,
    toggleFavoritesView,
    renderFavorites,
    loadFavorites,
    clearAllFavorites,
    toggleFavorite,
    addDeckSlidesToFavorites,
    toggleDeckBuilder,
    startNewDeck,
    sendChatMessage,
    confirmOutlineAndContinue,
    downloadDeck,
    downloadDeckAsCSV,
    switchPreviewTab,
    switchViewMode,
    addNewOutlineSlide
} from '../components/index.js';

import { renderCardGrid, attachSaveButtonListeners } from '../components/cards.js';
import { initNerdInfo } from '../components/deck-builder/nerd-info.js';

/** Debounce timer for search input */
let searchDebounceTimer = null;

/**
 * Sets up search input event listeners.
 */
function setupSearchListeners() {
    const searchInput = getById('q');
    
    if (!searchInput) return;
    
    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();
        clearTimeout(searchDebounceTimer);
        
        if (query.length >= 1) {
            enterSearchMode();
        }
        
        if (query.length < 2) {
            const results = getById('results');
            const resultsInfo = getById('results-info');
            const spinner = getById('search-spinner');
            
            if (results) results.innerHTML = '';
            resultsInfo?.classList.remove('visible');
            spinner?.classList.remove('active');
            
            if (query.length === 0) {
                exitSearchMode();
            }
            return;
        }
        
        searchDebounceTimer = setTimeout(() => search(query), 200);
    });
    
    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            clearTimeout(searchDebounceTimer);
            const query = searchInput.value.trim();
            if (query) {
                enterSearchMode();
            }
            search(query);
        }
    });
}

/**
 * Sets up filter button event listeners.
 */
function setupFilterListeners() {
    document.querySelectorAll('.filter-chip').forEach(btn => {
        btn.addEventListener('click', () => {
            toggleFilter(btn.dataset.filter);
        });
    });
}

/**
 * Sets up favorites-related event listeners.
 */
function setupFavoritesListeners() {
    getById('favorites-toggle')?.addEventListener('click', () => {
        toggleFavoritesView({
            onShow: () => {
                renderFavorites(renderCardGrid, () => {
                    attachSaveButtonListeners(toggleFavorite);
                });
            }
        });
    });
    
    getById('clear-favorites')?.addEventListener('click', () => {
        if (clearAllFavorites(true)) {
            renderFavorites(renderCardGrid, () => {
                attachSaveButtonListeners(toggleFavorite);
            });
        }
    });
}

/**
 * Sets up deck builder event listeners.
 */
function setupDeckBuilderListeners() {
    // Toggle deck builder
    getById('deckbuilder-toggle')?.addEventListener('click', toggleDeckBuilder);
    
    // Nerd info tab initialization (handles its own click events)
    initNerdInfo();
    
    // New deck button
    getById('new-deck-btn')?.addEventListener('click', startNewDeck);
    
    // Chat input
    const chatInput = getById('chat-input');
    if (chatInput) {
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendChatMessage();
            }
        });
    }
    
    // Chat send button
    getById('chat-send-btn')?.addEventListener('click', sendChatMessage);
    
    // Sample query buttons
    document.querySelectorAll('.sample-query-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const query = btn.dataset.query;
            if (query && !get('isAiProcessing')) {
                const input = getById('chat-input');
                if (input) {
                    input.value = query;
                    sendChatMessage();
                }
            }
        });
    });
    
    // Add deck slides to favorites
    getById('add-deck-to-favorites-btn')?.addEventListener('click', addDeckSlidesToFavorites);
    
    // Download PPTX
    getById('download-pptx-btn')?.addEventListener('click', downloadDeck);
    
    // Deck preview tabs
    document.querySelectorAll('.deck-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            switchPreviewTab(tab.dataset.tab);
        });
    });
    
    // View mode toggle
    document.querySelectorAll('.view-mode-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            switchViewMode(btn.dataset.mode);
        });
    });
    
    // Outline panel buttons
    getById('outline-confirm-btn')?.addEventListener('click', confirmOutlineAndContinue);
    getById('outline-add-slide-btn')?.addEventListener('click', addNewOutlineSlide);
    
    // Chat new deck button
    getById('chat-new-deck-btn')?.addEventListener('click', () => {
        startNewDeck();
    });
    
    // Chat inspect button - switches to sources tab
    getById('chat-inspect-btn')?.addEventListener('click', () => {
        switchPreviewTab('sources');
    });
    
    // Download buttons in sources tab
    document.addEventListener('click', (e) => {
        if (e.target.closest('#sources-download-csv-btn')) {
            downloadDeckAsCSV();
        } else if (e.target.closest('#sources-download-pptx-btn')) {
            downloadDeck();
        }
    });
}

/**
 * Sets up all event listeners.
 * Should be called once on DOM ready.
 */
export function setupEventListeners() {
    setupSearchListeners();
    setupFilterListeners();
    setupFavoritesListeners();
    setupDeckBuilderListeners();
}
