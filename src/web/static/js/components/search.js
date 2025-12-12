/**
 * Search Component
 * Handles search functionality including session ID detection.
 * @module components/search
 */

'use strict';

import { get, setState } from '../state/store.js';
import { getById, createElement } from '../utils/dom.js';
import { escapeHtml } from '../utils/dom.js';
import { getItem, setItem, STORAGE_KEYS } from '../utils/storage.js';
import { fetchSearchResults, fetchSessionSlides, isSessionId } from '../services/api.js';
import { renderCardGrid, renderEmptyState, attachSaveButtonListeners, renderSkeletonGrid, renderResultsInfoSkeleton } from './cards.js';
import { toggleFavorite } from './favorites.js';
import { loadAIOverview, hideAIOverview, showOverviewLoading } from './ai-overview.js';

const MAX_RECENT_QUERIES = 5;

function shouldShowRecentQueries() {
    const searchInput = getById('q');
    const resultsInfo = getById('results-info');

    // Show recent queries when:
    // 1. No query is typed in the search box
    // 2. Not currently showing search results
    const hasTypedQuery = !!searchInput?.value?.trim();
    const resultsVisible = resultsInfo?.classList?.contains('visible');

    return !hasTypedQuery && !resultsVisible;
}

function normalizeRecentQueries(value) {
    if (!Array.isArray(value)) return [];
    const cleaned = value
        .map(v => (typeof v === 'string' ? v.trim() : ''))
        .filter(Boolean);

    // De-dupe while preserving order
    const seen = new Set();
    return cleaned.filter(q => {
        if (seen.has(q)) return false;
        seen.add(q);
        return true;
    }).slice(0, MAX_RECENT_QUERIES);
}

function getRecentQueries() {
    return normalizeRecentQueries(getItem(STORAGE_KEYS.RECENT, []));
}

function setRecentQueries(queries) {
    setItem(STORAGE_KEYS.RECENT, normalizeRecentQueries(queries));
}

function renderRecentQueries() {
    const container = getById('recent-queries');
    if (!container) return;

    if (!shouldShowRecentQueries()) {
        container.innerHTML = '';
        container.classList.remove('visible');
        return;
    }

    const queries = getRecentQueries();
    container.innerHTML = '';

    if (!queries.length) {
        container.classList.remove('visible');
        return;
    }

    container.classList.add('visible');
    queries.forEach(query => {
        const btn = createElement('button', {
            className: 'recent-query-btn',
            type: 'button',
            dataset: { query }
        }, query);
        container.appendChild(btn);
    });
}

/**
 * Initializes the recent queries UI and click handling.
 * Safe to call multiple times.
 */
export function initRecentQueries() {
    const container = getById('recent-queries');
    if (!container) return;

    if (!container.dataset.bound) {
        container.addEventListener('click', (e) => {
            const btn = e.target.closest?.('.recent-query-btn');
            if (!btn) return;

            const query = btn.dataset.query?.trim();
            if (!query) return;

            const input = getById('q');
            if (input) input.value = query;
            enterSearchMode();
            recordRecentQuery(query);
            search(query, true);
        });
        container.dataset.bound = 'true';
    }

    renderRecentQueries();
}

/**
 * Records a query into the last-5 list (localStorage) and updates the UI.
 * @param {string} query - The search query
 */
export function recordRecentQuery(query) {
    const q = String(query || '').trim();
    if (q.length < 2) return;

    const current = getRecentQueries();
    const next = [q, ...current.filter(x => x !== q)].slice(0, MAX_RECENT_QUERIES);
    setRecentQueries(next);
    renderRecentQueries();
}

/**
 * Enters search mode (compact header UI).
 */
export function enterSearchMode() {
    if (!get('isInSearchMode')) {
        setState({ isInSearchMode: true });
        getById('hero')?.classList.add('searching');
    }
}

/**
 * Exits search mode if query is empty.
 */
export function exitSearchMode() {
    const searchInput = getById('q');
    if (get('isInSearchMode') && !searchInput?.value.trim()) {
        setState({ isInSearchMode: false });
        getById('hero')?.classList.remove('searching');
    }
}

/**
 * Filters results based on active event filters.
 * @param {Array} results - The results to filter
 * @returns {Array} Filtered results
 */
function filterResults(results) {
    const activeFilters = get('activeFilters');
    return results.filter(item => {
        const event = item.event.toLowerCase();
        if (event === 'build') return activeFilters.build;
        if (event === 'ignite') return activeFilters.ignite;
        return true;
    });
}

/**
 * Renders session view (all slides from one session).
 * @param {Object} data - Session data
 * @param {string} query - The session code query
 */
function renderSessionView(data, query) {
    const resultsContainer = getById('results');
    const resultsInfo = getById('results-info');
    
    // Hide AI overview for session views
    hideAIOverview();
    
    const slides = data.slides || [];
    const session = data.session;
    
    setState({ lastResults: slides });
    
    if (slides.length === 0) {
        resultsInfo?.classList.remove('visible');
        if (resultsContainer) {
            resultsContainer.innerHTML = renderEmptyState(
                '🔍',
                'Session not found',
                `No slides found for session ID "${query.toUpperCase()}"`
            );
        }
        return;
    }
    
    // Show session header info
    const eventClass = session?.event?.toLowerCase() || 'build';
    
    if (resultsInfo) {
        resultsInfo.innerHTML = `
            <div class="session-header-info">
                <span class="event-badge ${eventClass}">${escapeHtml(session?.event || 'Build')}</span>
                <strong>${escapeHtml(session?.session_code || query.toUpperCase())}</strong>
                <span class="session-title-text">${escapeHtml(session?.title || '')}</span>
            </div>
            <div class="results-count">
                <strong>${slides.length}</strong> slides in this session
                ${session?.ppt_url ? `<a href="${escapeHtml(session.ppt_url)}" class="session-download-btn" target="_blank" rel="noopener noreferrer">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        <polyline points="7 10 12 15 17 10"></polyline>
                        <line x1="12" y1="15" x2="12" y2="3"></line>
                    </svg>
                    Download PPTX
                </a>` : ''}
                ${session?.session_url ? `<a href="${escapeHtml(session.session_url)}" class="session-watch-btn" target="_blank" rel="noopener noreferrer">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                        <polygon points="5 3 19 12 5 21 5 3"></polygon>
                    </svg>
                    Watch Session
                </a>` : ''}
            </div>
        `;
        resultsInfo.classList.add('visible');
    }
    
    if (resultsContainer) {
        resultsContainer.innerHTML = renderCardGrid(slides);
        attachSaveButtonListeners(toggleFavorite);
    }
}

/**
 * Renders search results.
 * @param {Object} data - Search data
 */
function renderSearchResults(data) {
    const resultsContainer = getById('results');
    const resultsInfo = getById('results-info');
    
    const filteredResults = filterResults(data.results);
    setState({ lastResults: filteredResults });
    
    if (filteredResults.length === 0) {
        resultsInfo?.classList.remove('visible');
        hideAIOverview();
        
        const hasResults = data.results.length > 0;
        if (resultsContainer) {
            resultsContainer.innerHTML = renderEmptyState(
                hasResults ? '🔘' : '🔍',
                hasResults ? 'No results with current filters' : 'No results found',
                hasResults ? 'Try enabling both Build and Ignite filters' : 'Try different keywords or check your spelling'
            );
        }
        return;
    }
    
    const uniqueDecks = new Set(filteredResults.map(r => r.session_code)).size;
    
    if (resultsInfo) {
        resultsInfo.classList.remove('skeleton-loading');
        resultsInfo.innerHTML = `
            <div class="results-count">Found <strong>${filteredResults.length}</strong> matching slides in <strong>${uniqueDecks}</strong> decks</div>
            <div class="results-time">
                <span class="time-badge">⚡ ${data.search_time_ms}ms</span>
            </div>
        `;
        resultsInfo.classList.add('visible');
    }
    
    if (resultsContainer) {
        resultsContainer.innerHTML = renderCardGrid(filteredResults);
        attachSaveButtonListeners(toggleFavorite);
    }
    
    // Load AI overview asynchronously
    if (data.search_context && data.query) {
        loadAIOverview(
            data.query,
            data.search_context,
            filteredResults.length,
            uniqueDecks
        );
    } else {
        hideAIOverview();
    }
}

/**
 * Performs a search query.
 * @param {string} query - The search query
 * @param {boolean} [force=false] - Force search even if query matches last
 */
export async function search(query, force = false) {
    const resultsContainer = getById('results');
    const resultsInfo = getById('results-info');
    const spinner = getById('search-spinner');
    const searchContainer = document.querySelector('.search-container');
    
    // Clear results for short queries
    if (!query || query.length < 2) {
        if (resultsContainer) resultsContainer.innerHTML = '';
        resultsInfo?.classList.remove('visible');
        hideAIOverview();
        setState({
            lastRenderedQuery: '',
            lastResults: []
        });
        renderRecentQueries();
        return;
    }
    
    // Skip if same query (unless forced)
    if (query === get('lastRenderedQuery') && !force) {
        spinner?.classList.remove('active');
        return;
    }
    
    // Queue query if already searching
    if (get('isSearching')) {
        setState({ pendingQuery: query });
        return;
    }
    
    setState({
        currentQuery: query,
        isSearching: true
    });
    
    // Show skeleton loading states immediately
    showOverviewLoading();
    
    if (resultsInfo) {
        resultsInfo.innerHTML = renderResultsInfoSkeleton();
        resultsInfo.classList.add('visible');
    }
    
    if (resultsContainer) {
        resultsContainer.innerHTML = renderSkeletonGrid(8);
    }
    
    // Show spinner and start color transition (green → blue)
    spinner?.classList.add('active');
    searchContainer?.classList.add('searching');
    searchContainer?.classList.remove('color-transitioning');
    
    // Start color shift after a frame (so green is rendered first)
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            spinner?.classList.add('color-shifted');
            searchContainer?.classList.add('color-transitioning');
        });
    });
    
    try {
        let data;
        const isSession = isSessionId(query);
        
        if (isSession) {
            data = await fetchSessionSlides(query);
            renderSessionView(data, query);
        } else {
            data = await fetchSearchResults(query);
            renderSearchResults(data);
        }
        
        setState({
            lastRenderedQuery: query,
            isSearching: false
        });

        // Hide recent queries once we have results on screen.
        renderRecentQueries();
        
        // Process pending query if any
        const pendingQuery = get('pendingQuery');
        if (pendingQuery && pendingQuery !== query) {
            setState({ pendingQuery: null });
            search(pendingQuery);
            return;
        }
        setState({ pendingQuery: null });
        
    } catch (error) {
        console.error('[Search] Error:', error);
        
        setState({ isSearching: false });
        resultsInfo?.classList.remove('visible');
        
        if (resultsContainer) {
            resultsContainer.innerHTML = renderEmptyState(
                '⚠️',
                'Something went wrong',
                error.message
            );
        }
    } finally {
        spinner?.classList.remove('active');
        spinner?.classList.remove('color-shifted');
        searchContainer?.classList.remove('searching');
        searchContainer?.classList.remove('color-transitioning');
    }
}

/**
 * Re-searches with current query (after filter change).
 */
export function refreshSearch() {
    const lastQuery = get('lastRenderedQuery');
    if (lastQuery) {
        search(lastQuery, true);
    }
}

/**
 * Toggles an event filter.
 * @param {string} filter - The filter name ('build' or 'ignite')
 */
export function toggleFilter(filter) {
    const activeFilters = { ...get('activeFilters') };
    activeFilters[filter] = !activeFilters[filter];
    
    // Ensure at least one filter is active
    if (!activeFilters.build && !activeFilters.ignite) {
        activeFilters[filter] = true;
    }
    
    setState({ activeFilters });
    
    // Update UI
    document.querySelectorAll('.filter-chip').forEach(btn => {
        const f = btn.dataset.filter;
        btn.classList.toggle('active', activeFilters[f]);
        btn.setAttribute('aria-pressed', activeFilters[f]);
    });
    
    refreshSearch();
}
