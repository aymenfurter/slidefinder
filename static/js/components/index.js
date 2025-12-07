/**
 * Components Module Index
 * Re-exports all component modules.
 * @module components
 */

'use strict';

// Card rendering
export { renderCard, renderCardGrid, renderEmptyState, updateSaveButtons, attachSaveButtonListeners } from './cards.js';

// Favorites management
export {
    loadFavorites,
    saveFavorites,
    updateFavoritesCount,
    isFavorite,
    toggleFavorite,
    addDeckSlidesToFavorites,
    clearAllFavorites,
    toggleFavoritesView,
    renderFavorites
} from './favorites.js';

// Search functionality
export {
    enterSearchMode,
    exitSearchMode,
    search,
    refreshSearch,
    toggleFilter
} from './search.js';

// Deck builder
export {
    showDeckBuilder,
    toggleDeckBuilder,
    startNewDeck,
    sendChatMessage,
    confirmOutlineAndContinue,
    downloadDeck,
    switchPreviewTab,
    switchViewMode,
    addNewOutlineSlide
} from './deck-builder/index.js';

// Disclaimer
export { initDisclaimer } from './disclaimer.js';
