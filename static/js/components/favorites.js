/**
 * Favorites Management Component
 * Handles saving, loading, and displaying favorite slides.
 * @module components/favorites
 */

'use strict';

import { get, setState } from '../state/store.js';
import { getItem, setItem, STORAGE_KEYS } from '../utils/storage.js';
import { showToast } from '../utils/toast.js';
import { getById } from '../utils/dom.js';
import { updateSaveButtons } from './cards.js';

/**
 * Loads favorites from localStorage into state.
 */
export function loadFavorites() {
    const favorites = getItem(STORAGE_KEYS.FAVORITES, []);
    setState({ favorites });
    updateFavoritesCount();
}

/**
 * Saves current favorites to localStorage.
 */
export function saveFavorites() {
    const favorites = get('favorites') || [];
    setItem(STORAGE_KEYS.FAVORITES, favorites);
    updateFavoritesCount();
}

/**
 * Updates the favorites count badge in the UI.
 */
export function updateFavoritesCount() {
    const countEl = getById('favorites-count');
    const favorites = get('favorites') || [];
    
    if (countEl) {
        countEl.textContent = favorites.length;
    }
}

/**
 * Checks if a slide is in favorites.
 * @param {string} slideId - The slide ID to check
 * @returns {boolean} True if the slide is a favorite
 */
export function isFavorite(slideId) {
    const favorites = get('favorites') || [];
    return favorites.some(f => f.slide_id === slideId);
}

/**
 * Toggles a slide's favorite status.
 * @param {Object} slideData - The slide data
 */
export function toggleFavorite(slideData) {
    const favorites = [...(get('favorites') || [])];
    const idx = favorites.findIndex(f => f.slide_id === slideData.slide_id);
    
    if (idx >= 0) {
        favorites.splice(idx, 1);
    } else {
        favorites.push({
            ...slideData,
            saved_at: Date.now()
        });
    }
    
    setState({ favorites });
    saveFavorites();
    updateSaveButtons();
}

/**
 * Adds all deck slides to favorites.
 * @returns {number} The number of slides added
 */
export function addDeckSlidesToFavorites() {
    const deckSlides = get('deckSlides') || [];
    
    if (!deckSlides || deckSlides.length === 0) {
        showToast('No slides in deck to add');
        return 0;
    }
    
    const favorites = [...(get('favorites') || [])];
    let addedCount = 0;
    
    deckSlides.forEach(slide => {
        const slideData = {
            slide_id: `${slide.session_code}_${slide.slide_number}`,
            session_code: slide.session_code,
            slide_number: slide.slide_number,
            title: slide.title || slide.session_code,
            content: slide.reason || '',
            event: slide.event || 'Build',
            session_url: slide.session_url || '',
            ppt_url: slide.ppt_url || '',
            has_thumbnail: true
        };
        
        if (!isFavorite(slideData.slide_id)) {
            favorites.push({
                ...slideData,
                saved_at: Date.now()
            });
            addedCount++;
        }
    });
    
    setState({ favorites });
    saveFavorites();
    
    // Update button appearance
    const btn = getById('add-deck-to-favorites-btn');
    if (btn) {
        btn.classList.add('added');
        const svg = btn.querySelector('svg');
        if (svg) {
            svg.setAttribute('fill', 'currentColor');
        }
    }
    
    if (addedCount > 0) {
        showToast(`Added ${addedCount} slide${addedCount > 1 ? 's' : ''} to favorites`);
    } else {
        showToast('All slides already in favorites');
    }
    
    return addedCount;
}

/**
 * Clears all favorites.
 * @param {boolean} [confirm=true] - Whether to show confirmation dialog
 * @returns {boolean} True if favorites were cleared
 */
export function clearAllFavorites(confirm = true) {
    if (confirm && !window.confirm('Remove all saved slides?')) {
        return false;
    }
    
    setState({ favorites: [] });
    saveFavorites();
    return true;
}

/**
 * Toggles the favorites view visibility.
 * @param {Object} callbacks - Callback functions
 * @param {Function} callbacks.onShow - Called when favorites view is shown
 * @param {Function} callbacks.onHide - Called when favorites view is hidden
 */
export function toggleFavoritesView(callbacks = {}) {
    const showingFavorites = get('showingFavorites');
    const newState = !showingFavorites;
    
    setState({ showingFavorites: newState });
    
    const favSection = getById('favorites-section');
    const mainContent = getById('main-content');
    const deckSection = getById('deck-builder-section');
    const heroEl = getById('hero');
    const toggleBtn = getById('favorites-toggle');
    const deckBtn = getById('deckbuilder-toggle');
    
    // Hide deck builder when showing favorites
    if (deckSection) {
        deckSection.style.display = 'none';
    }
    
    if (newState) {
        if (favSection) favSection.classList.add('visible');
        if (mainContent) mainContent.classList.add('hidden');
        if (heroEl) heroEl.style.display = 'none';
        if (toggleBtn) toggleBtn.classList.add('active');
        if (deckBtn) deckBtn.classList.remove('active');
        
        if (callbacks.onShow) {
            callbacks.onShow();
        }
    } else {
        if (favSection) favSection.classList.remove('visible');
        if (mainContent) mainContent.classList.remove('hidden');
        if (heroEl) heroEl.style.display = '';
        if (toggleBtn) toggleBtn.classList.remove('active');
        
        if (callbacks.onHide) {
            callbacks.onHide();
        }
    }
}

/**
 * Renders the favorites grid.
 * @param {Function} renderCardGrid - Function to render card grid
 * @param {Function} attachListeners - Function to attach save button listeners
 */
export function renderFavorites(renderCardGrid, attachListeners) {
    const container = getById('favorites-grid');
    if (!container) return;
    
    const favorites = get('favorites') || [];
    
    if (favorites.length === 0) {
        container.innerHTML = `
            <div class="favorites-empty">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
                    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
                </svg>
                <h3>No saved slides yet</h3>
                <p>Click the heart icon on any slide to save it here</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = renderCardGrid(favorites);
    
    if (attachListeners) {
        attachListeners();
    }
}
