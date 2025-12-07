/**
 * Application State Store
 * Centralized state management with pub/sub pattern for reactivity.
 * @module state/store
 */

'use strict';

/**
 * @typedef {Object} SearchState
 * @property {string} currentQuery - Current search query
 * @property {string} lastRenderedQuery - Last successfully rendered query
 * @property {Map<string, Object>} prefetchCache - Query results cache
 * @property {boolean} isSearching - Whether a search is in progress
 * @property {string|null} pendingQuery - Query waiting to be executed
 * @property {boolean} isInSearchMode - Whether search mode UI is active
 * @property {Object} activeFilters - Active event filters
 * @property {Array} lastResults - Last search results
 */

/**
 * @typedef {Object} DeckBuilderState
 * @property {string|null} deckSessionId - Current deck builder session ID
 * @property {Array} deckSlides - Current deck slides
 * @property {Array} deckSources - Source decks for download
 * @property {Object} slideReviews - Slide review status map
 * @property {boolean} isAiProcessing - Whether AI is processing
 * @property {string} activePreviewTab - Active preview tab ('preview' or 'sources')
 * @property {string} viewMode - View mode ('compact' or 'large')
 * @property {Object|null} pendingOutline - Outline awaiting confirmation
 * @property {Array|null} allSlidesForOutline - Available slides for outline
 * @property {boolean} outlineConfirmed - Whether outline has been confirmed
 */

/**
 * @typedef {Object} FavoritesState
 * @property {Array} favorites - Saved slides
 * @property {boolean} showingFavorites - Whether favorites view is active
 */

/**
 * @typedef {Object} AppState
 * @property {SearchState} search - Search-related state
 * @property {DeckBuilderState} deckBuilder - Deck builder state
 * @property {FavoritesState} favorites - Favorites state
 */

/**
 * Creates the initial application state.
 * @returns {AppState} The initial state object
 */
function createInitialState() {
    return {
        // Search state
        currentQuery: '',
        lastRenderedQuery: '',
        prefetchCache: new Map(),
        isSearching: false,
        pendingQuery: null,
        isInSearchMode: false,
        activeFilters: { build: true, ignite: true },
        lastResults: [],
        
        // Deck Builder state
        deckSessionId: null,
        deckSlides: [],
        deckSources: [],
        slideReviews: {},
        isAiProcessing: false,
        activePreviewTab: 'preview',
        viewMode: 'compact',
        
        // Outline state
        pendingOutline: null,
        allSlidesForOutline: null,
        outlineConfirmed: false,
        
        // Favorites state
        favorites: [],
        showingFavorites: false
    };
}

/** @type {AppState} */
let state = createInitialState();

/** @type {Map<string, Set<Function>>} */
const listeners = new Map();

/**
 * Gets the current application state.
 * Returns a shallow copy to prevent direct mutation.
 * @returns {AppState} The current state
 */
export function getState() {
    return { ...state };
}

/**
 * Gets a specific value from state.
 * @param {string} key - The state key
 * @returns {*} The value or undefined
 */
export function get(key) {
    return state[key];
}

/**
 * Updates the application state and notifies listeners.
 * @param {Partial<AppState>} updates - The state updates to apply
 */
export function setState(updates) {
    const changedKeys = [];
    
    Object.entries(updates).forEach(([key, value]) => {
        if (state[key] !== value) {
            changedKeys.push(key);
            state[key] = value;
        }
    });
    
    // Notify listeners for changed keys
    changedKeys.forEach(key => {
        const keyListeners = listeners.get(key);
        if (keyListeners) {
            keyListeners.forEach(callback => {
                try {
                    callback(state[key], key);
                } catch (error) {
                    console.error(`[Store] Listener error for "${key}":`, error);
                }
            });
        }
    });
    
    // Notify global listeners
    if (changedKeys.length > 0) {
        const globalListeners = listeners.get('*');
        if (globalListeners) {
            globalListeners.forEach(callback => {
                try {
                    callback(state, changedKeys);
                } catch (error) {
                    console.error('[Store] Global listener error:', error);
                }
            });
        }
    }
}

/**
 * Subscribes to state changes.
 * @param {string|string[]} keys - The state key(s) to watch, or '*' for all changes
 * @param {Function} callback - The callback function
 * @returns {Function} Unsubscribe function
 */
export function subscribe(keys, callback) {
    const keyArray = Array.isArray(keys) ? keys : [keys];
    
    keyArray.forEach(key => {
        if (!listeners.has(key)) {
            listeners.set(key, new Set());
        }
        listeners.get(key).add(callback);
    });
    
    // Return unsubscribe function
    return () => {
        keyArray.forEach(key => {
            const keyListeners = listeners.get(key);
            if (keyListeners) {
                keyListeners.delete(callback);
            }
        });
    };
}

/**
 * Resets the state to initial values.
 * Useful for testing or resetting the application.
 */
export function resetState() {
    state = createInitialState();
    
    // Notify all listeners of reset
    const globalListeners = listeners.get('*');
    if (globalListeners) {
        globalListeners.forEach(callback => {
            try {
                callback(state, Object.keys(state));
            } catch (error) {
                console.error('[Store] Reset listener error:', error);
            }
        });
    }
}

/**
 * Resets deck builder state for starting a new deck.
 */
export function resetDeckBuilder() {
    setState({
        deckSessionId: null,
        deckSlides: [],
        deckSources: [],
        slideReviews: {},
        pendingOutline: null,
        allSlidesForOutline: null,
        outlineConfirmed: false
    });
}

/**
 * Updates the prefetch cache.
 * Maintains cache size limit of 50 entries.
 * @param {string} key - Cache key
 * @param {*} value - Value to cache
 */
export function updateCache(key, value) {
    const cache = state.prefetchCache;
    cache.set(key, value);
    
    // Maintain cache size limit
    if (cache.size > 50) {
        const firstKey = cache.keys().next().value;
        cache.delete(firstKey);
    }
}

/**
 * Gets a value from the prefetch cache.
 * @param {string} key - Cache key
 * @returns {*} Cached value or undefined
 */
export function getFromCache(key) {
    return state.prefetchCache.get(key);
}

/**
 * Checks if a key exists in the cache.
 * @param {string} key - Cache key
 * @returns {boolean} True if cached
 */
export function hasInCache(key) {
    return state.prefetchCache.has(key);
}

// Export a singleton store object for convenient access
const store = {
    getState,
    get,
    setState,
    subscribe,
    resetState,
    resetDeckBuilder,
    updateCache,
    getFromCache,
    hasInCache
};

export default store;
