/**
 * Card Rendering Component
 * Renders slide cards for search results and favorites.
 * @module components/cards
 */

'use strict';

import { escapeHtml } from '../utils/dom.js';
import { get } from '../state/store.js';

/**
 * Checks if a slide is in favorites.
 * Defined here to avoid circular dependency with favorites.js
 * @param {string} slideId - The slide ID to check
 * @returns {boolean} True if the slide is a favorite
 */
function isFavorite(slideId) {
    const favorites = get('favorites') || [];
    return favorites.some(f => f.slide_id === slideId);
}

/**
 * Renders a single slide card.
 * @param {Object} item - The slide data
 * @param {string} item.slide_id - Unique slide identifier
 * @param {string} item.session_code - Session code
 * @param {number} item.slide_number - Slide number
 * @param {string} item.title - Slide title
 * @param {string} [item.content] - Slide content
 * @param {string} [item.snippet] - Search snippet with highlights
 * @param {string} item.event - Event name (Build/Ignite)
 * @param {string} item.session_url - Session watch URL
 * @param {string} [item.ppt_url] - PowerPoint download URL
 * @param {boolean} [item.has_thumbnail] - Whether thumbnail exists
 * @returns {string} The card HTML
 */
export function renderCard(item) {
    const thumbUrl = `/thumbnails/${item.session_code}_${item.slide_number}.png`;
    const safeTitle = escapeHtml(item.title);
    const safeContent = escapeHtml((item.content || '').substring(0, 200));
    const eventClass = item.event.toLowerCase();
    const isSaved = isFavorite(item.slide_id);
    
    // Safely encode slide data for data attribute
    const slideDataJson = JSON.stringify(item).replace(/'/g, '&#39;');
    
    return `
    <div class="card ${eventClass}">
        <div class="slide-preview">
            <button class="save-btn ${isSaved ? 'saved' : ''}" 
                    data-slide-id="${escapeHtml(item.slide_id)}"
                    data-slide='${slideDataJson}'
                    title="${isSaved ? 'Remove from favorites' : 'Save to favorites'}"
                    aria-label="${isSaved ? 'Remove from favorites' : 'Save to favorites'}">
                <svg viewBox="0 0 24 24" fill="${isSaved ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
            </button>
            <div class="slide-badge">Slide ${item.slide_number}</div>
            ${!item.has_thumbnail ? '<div class="no-thumb-badge">No preview</div>' : ''}
            <img src="${thumbUrl}" 
                 onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"
                 alt="Slide ${item.slide_number} preview"
                 loading="lazy">
            <div class="slide-preview-fallback" style="display:none;">
                <div class="preview-title">${safeTitle}</div>
                <div class="preview-text">${safeContent}</div>
            </div>
        </div>
        <div class="card-body">
            <div class="card-meta">
                <span class="event-badge ${eventClass}">${escapeHtml(item.event)}</span>
                <span class="session-code">${escapeHtml(item.session_code)}</span>
            </div>
            <a href="${escapeHtml(item.session_url)}" target="_blank" rel="noopener noreferrer" class="card-title">${safeTitle}</a>
            <div class="card-snippet">${item.snippet || safeContent || ''}</div>
            <div class="card-actions">
                <a href="${escapeHtml(item.session_url)}" target="_blank" rel="noopener noreferrer" class="action-btn">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                    Watch
                </a>
                ${item.ppt_url ? `<a href="${escapeHtml(item.ppt_url)}" target="_blank" rel="noopener noreferrer" class="action-btn">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                    Download
                </a>` : ''}
            </div>
        </div>
    </div>
    `;
}

/**
 * Renders multiple cards in a grid.
 * @param {Array<Object>} items - The slide items to render
 * @returns {string} The grid HTML
 */
export function renderCardGrid(items) {
    if (!items || items.length === 0) {
        return '';
    }
    return '<div class="grid">' + items.map(item => renderCard(item)).join('') + '</div>';
}

/**
 * Renders an empty state message.
 * @param {string} icon - The emoji icon
 * @param {string} title - The title message
 * @param {string} message - The description message
 * @returns {string} The empty state HTML
 */
export function renderEmptyState(icon, title, message) {
    return `
        <div class="empty-state">
            <div class="empty-icon">${icon}</div>
            <h3>${escapeHtml(title)}</h3>
            <p>${escapeHtml(message)}</p>
        </div>
    `;
}

/**
 * Updates all save buttons to reflect current favorites state.
 */
export function updateSaveButtons() {
    document.querySelectorAll('.save-btn').forEach(btn => {
        const slideId = btn.dataset.slideId;
        const isSaved = isFavorite(slideId);
        
        btn.classList.toggle('saved', isSaved);
        btn.title = isSaved ? 'Remove from favorites' : 'Save to favorites';
        btn.setAttribute('aria-label', isSaved ? 'Remove from favorites' : 'Save to favorites');
        
        const svg = btn.querySelector('svg');
        if (svg) {
            svg.setAttribute('fill', isSaved ? 'currentColor' : 'none');
        }
    });
}

/**
 * Attaches click listeners to save buttons.
 * Uses event delegation pattern to avoid duplicate listeners.
 * @param {Function} onToggle - Callback when a favorite is toggled
 */
export function attachSaveButtonListeners(onToggle) {
    document.querySelectorAll('.save-btn').forEach(btn => {
        if (btn.dataset.listenerAttached) return;
        btn.dataset.listenerAttached = 'true';
        
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            try {
                const slideData = JSON.parse(btn.dataset.slide.replace(/&#39;/g, "'"));
                onToggle(slideData);
            } catch (error) {
                console.error('[Cards] Failed to parse slide data:', error);
            }
        });
    });
}
