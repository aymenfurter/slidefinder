/**
 * Deck Preview Component
 * Handles the deck preview and sources display.
 * @module components/deck-builder/preview
 */

'use strict';

import { escapeHtml, getById } from '../../utils/dom.js';
import { get, setState } from '../../state/store.js';

/**
 * Updates the deck preview with slides.
 * @param {Array|null} slides - The slides to display (null to use existing)
 * @param {boolean} [isNewSlides=false] - Whether these are newly added slides
 */
export function updateDeckPreview(slides, isNewSlides = false) {
    const previewContent = getById('deck-preview-content');
    const slideCount = getById('deck-slide-count');
    
    if (!previewContent) return;
    
    // Update state with new slides
    if (slides) {
        setState({ deckSlides: slides });
    }
    
    const currentSlides = get('deckSlides') || [];
    const viewMode = get('viewMode') || 'compact';
    const slideReviews = get('slideReviews') || {};
    
    // Apply view mode class
    previewContent.classList.toggle('large-view', viewMode === 'large');
    
    if (!currentSlides || currentSlides.length === 0) {
        previewContent.innerHTML = `
            <div class="deck-empty">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
                    <rect x="2" y="3" width="20" height="14" rx="2"></rect>
                    <line x1="8" y1="21" x2="16" y2="21"></line>
                    <line x1="12" y1="17" x2="12" y2="21"></line>
                </svg>
                <h4>No slides yet</h4>
                <p>Start chatting to build your custom deck</p>
            </div>
        `;
        if (slideCount) slideCount.style.display = 'none';
        return;
    }
    
    if (slideCount) {
        slideCount.textContent = `${currentSlides.length} slides`;
        slideCount.style.display = 'inline';
    }
    
    // Show/hide download button
    const downloadBtn = getById('download-pptx-btn');
    if (downloadBtn) {
        downloadBtn.style.display = currentSlides.length > 0 ? 'flex' : 'none';
    }
    
    // Show/hide add to favorites button
    const addToFavBtn = getById('add-deck-to-favorites-btn');
    if (addToFavBtn) {
        addToFavBtn.style.display = currentSlides.length > 0 ? 'flex' : 'none';
        addToFavBtn.classList.remove('added');
        const svg = addToFavBtn.querySelector('svg');
        if (svg) svg.setAttribute('fill', 'none');
    }
    
    // Helper to get slide review status badge
    function getSlideStatusBadge(slide) {
        const slideKey = `${slide.session_code}_${slide.slide_number}`;
        const review = slideReviews[slideKey];
        if (!review) return '';
        
        if (review.status === 'approved') {
            return '<span class="slide-status-badge approved" title="Approved">✓</span>';
        } else if (review.status === 'to-be-replaced') {
            return `<span class="slide-status-badge replace" title="${escapeHtml(review.reason || 'To be replaced')}">🔄</span>`;
        }
        return '';
    }
    
    // Render based on view mode
    if (viewMode === 'large') {
        previewContent.innerHTML = `
            <div class="deck-slides-list">
                ${currentSlides.map((slide, idx) => `
                    <div class="deck-slide-item${isNewSlides ? ' new-slide' : ''}">
                        <div class="deck-slide-header">
                            <div class="deck-slide-number">${idx + 1}</div>
                            <div class="deck-slide-code">${escapeHtml(slide.session_code)} #${slide.slide_number}</div>
                            ${getSlideStatusBadge(slide)}
                        </div>
                        <img class="deck-slide-thumb" 
                             src="/thumbnails/${encodeURIComponent(slide.session_code)}_${slide.slide_number}.png"
                             onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 16 9%22><rect fill=%22%23333%22 width=%2216%22 height=%229%22/></svg>'"
                             alt="Slide ${slide.slide_number}"
                             loading="lazy">
                        <div class="deck-slide-info">
                            <div class="deck-slide-reason">${escapeHtml(slide.reason || '')}</div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    } else {
        previewContent.innerHTML = `
            <div class="deck-slides-list">
                ${currentSlides.map((slide, idx) => `
                    <div class="deck-slide-item${isNewSlides ? ' new-slide' : ''}">
                        <div class="deck-slide-number">${idx + 1}${getSlideStatusBadge(slide)}</div>
                        <img class="deck-slide-thumb" 
                             src="/thumbnails/${encodeURIComponent(slide.session_code)}_${slide.slide_number}.png"
                             onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 16 9%22><rect fill=%22%23333%22 width=%2216%22 height=%229%22/></svg>'"
                             alt="Slide ${slide.slide_number}"
                             loading="lazy">
                        <div class="deck-slide-info">
                            <div class="deck-slide-code">${escapeHtml(slide.session_code)} #${slide.slide_number}</div>
                            <div class="deck-slide-reason">${escapeHtml(slide.reason || '')}</div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }
    
    // Auto-scroll to show new slides
    previewContent.scrollTop = previewContent.scrollHeight;
}

/**
 * Updates the source decks display.
 * @param {Array} decks - The source decks
 */
export function updateSourceDecks(decks) {
    const sourcesContent = getById('deck-sources-content');
    
    if (!sourcesContent) return;
    
    setState({ deckSources: decks || [] });
    
    if (!decks || decks.length === 0) {
        sourcesContent.innerHTML = `
            <div class="deck-empty">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="7 10 12 15 17 10"></polyline>
                    <line x1="12" y1="15" x2="12" y2="3"></line>
                </svg>
                <h4>No source decks yet</h4>
                <p>Build a deck to see downloadable sources</p>
            </div>
        `;
        return;
    }
    
    sourcesContent.innerHTML = `
        <div class="download-list">
            ${decks.map(deck => `
                <div class="download-item">
                    <div class="download-item-info">
                        <span class="download-item-code">${escapeHtml(deck.session_code)}</span>
                        <span class="download-item-title">${escapeHtml(deck.title)}</span>
                        <span class="download-item-slides">${deck.slides_used.length} slides used</span>
                    </div>
                    ${deck.ppt_url ? `<a href="${escapeHtml(deck.ppt_url)}" class="download-item-btn" target="_blank" rel="noopener noreferrer" aria-label="Download ${escapeHtml(deck.session_code)}">
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                            <polyline points="7 10 12 15 17 10"></polyline>
                            <line x1="12" y1="15" x2="12" y2="3"></line>
                        </svg>
                    </a>` : ''}
                </div>
            `).join('')}
        </div>
    `;
}

/**
 * Switches the preview tab.
 * @param {string} tabName - The tab to switch to ('preview' or 'sources')
 */
export function switchPreviewTab(tabName) {
    setState({ activePreviewTab: tabName });
    
    const previewContent = getById('deck-preview-content');
    const sourcesContent = getById('deck-sources-content');
    
    document.querySelectorAll('.deck-tab').forEach(tab => {
        const isActive = tab.dataset.tab === tabName;
        tab.classList.toggle('active', isActive);
        tab.setAttribute('aria-selected', isActive);
    });
    
    if (tabName === 'preview') {
        if (previewContent) previewContent.style.display = '';
        if (sourcesContent) sourcesContent.style.display = 'none';
    } else {
        if (previewContent) previewContent.style.display = 'none';
        if (sourcesContent) sourcesContent.style.display = '';
    }
}

/**
 * Switches the view mode.
 * @param {string} mode - The view mode ('compact' or 'large')
 */
export function switchViewMode(mode) {
    setState({ viewMode: mode });
    
    document.querySelectorAll('.view-mode-btn').forEach(btn => {
        const isActive = btn.dataset.mode === mode;
        btn.classList.toggle('active', isActive);
        btn.setAttribute('aria-pressed', isActive);
    });
    
    // Re-render the deck preview with new view mode
    updateDeckPreview(null, false);
}

/**
 * Updates intermediate deck during building.
 * @param {Array} deck - The current deck slides
 * @param {string} narrative - The narrative
 * @param {number} revisionRound - The revision round
 * @param {boolean} isFinal - Whether this is the final deck
 */
export function updateIntermediateDeck(deck, narrative, revisionRound, isFinal) {
    if (deck && deck.length > 0) {
        updateDeckPreview(deck, true);
    }
}
