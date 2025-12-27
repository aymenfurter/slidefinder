/**
 * Components Module Index
 * Re-exports all component modules.
 * @module components
 */

'use strict';

// Card rendering
export { renderCard, renderCardGrid, renderEmptyState, updateSaveButtons, attachSaveButtonListeners, renderSkeletonGrid, renderResultsInfoSkeleton } from './cards.js';

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
    toggleFilter,
    initRecentQueries,
    recordRecentQuery
} from './search.js';

// AI Overview
export {
    loadAIOverview,
    hideAIOverview,
    showOverviewLoading
} from './ai-overview.js';

// Deck builder
export {
    showDeckBuilder,
    toggleDeckBuilder,
    startNewDeck,
    sendChatMessage,
    confirmOutlineAndContinue,
    downloadDeck,
    downloadDeckAsCSV,
    switchPreviewTab,
    switchViewMode,
    addNewOutlineSlide
} from './deck-builder/index.js';

// Disclaimer
export { initDisclaimer } from './disclaimer.js';

// Animated Logo
export { AnimatedLogo, initAnimatedLogo } from './animated-logo.js';

// Slide Assistant
export {
    toggleSlideAssistant,
    sendAssistantMessage,
    clearAssistantChat,
    initSlideAssistant
} from './slide-assistant.js';
