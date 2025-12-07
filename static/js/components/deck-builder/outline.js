/**
 * Outline Panel Component
 * Handles the editable outline for deck building.
 * @module components/deck-builder/outline
 */

'use strict';

import { escapeHtml, getById } from '../../utils/dom.js';
import { get, setState } from '../../state/store.js';

/**
 * Shows the editable outline panel.
 * @param {string} title - Presentation title
 * @param {string} narrative - Presentation narrative
 * @param {Array} slides - Slide definitions
 */
export function showOutlinePanel(title, narrative, slides) {
    const outlinePanel = getById('outline-panel');
    const titleInput = getById('outline-title-input');
    const narrativeInput = getById('outline-narrative-input');
    const slidesContainer = getById('outline-slides-editable');
    
    if (!outlinePanel) return;
    
    // Populate the panel
    if (titleInput) titleInput.value = title;
    if (narrativeInput) narrativeInput.value = narrative;
    
    // Clear and populate slides
    if (slidesContainer) {
        slidesContainer.innerHTML = '';
        slides.forEach((slide, index) => {
            addOutlineSlideItem(slide, index + 1);
        });
    }
    
    // Show the panel
    outlinePanel.style.display = 'block';
    
    // Hide chat input while editing outline
    const chatInputArea = getById('chat-input-area');
    if (chatInputArea) {
        chatInputArea.style.display = 'none';
    }
}

/**
 * Hides the outline panel.
 */
export function hideOutlinePanel() {
    const outlinePanel = getById('outline-panel');
    if (outlinePanel) {
        outlinePanel.style.display = 'none';
    }
}

/**
 * Adds a slide item to the editable outline.
 * @param {Object} slide - The slide data
 * @param {number} position - The slide position
 */
export function addOutlineSlideItem(slide, position) {
    const container = getById('outline-slides-editable');
    if (!container) return;
    
    const item = document.createElement('div');
    item.className = 'outline-slide-item';
    item.dataset.position = position;
    item.dataset.searchHints = JSON.stringify(slide.search_hints || []);
    
    item.innerHTML = `
        <div class="outline-slide-number">${position}</div>
        <div class="outline-slide-content">
            <input type="text" class="outline-slide-topic-input" value="${escapeHtml(slide.topic)}" placeholder="Slide topic..." aria-label="Slide ${position} topic">
            <input type="text" class="outline-slide-purpose-input" value="${escapeHtml(slide.purpose)}" placeholder="Purpose..." aria-label="Slide ${position} purpose">
        </div>
        <button class="outline-slide-remove-btn" data-position="${position}" title="Remove slide" aria-label="Remove slide ${position}">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
        </button>
    `;
    
    // Attach remove button listener
    const removeBtn = item.querySelector('.outline-slide-remove-btn');
    if (removeBtn) {
        removeBtn.addEventListener('click', () => {
            item.remove();
            renumberOutlineSlides();
        });
    }
    
    container.appendChild(item);
}

/**
 * Renumbers all outline slides after removal.
 */
export function renumberOutlineSlides() {
    const items = document.querySelectorAll('#outline-slides-editable .outline-slide-item');
    items.forEach((item, index) => {
        const position = index + 1;
        item.dataset.position = position;
        
        const numEl = item.querySelector('.outline-slide-number');
        if (numEl) numEl.textContent = position;
        
        const topicInput = item.querySelector('.outline-slide-topic-input');
        if (topicInput) topicInput.setAttribute('aria-label', `Slide ${position} topic`);
        
        const purposeInput = item.querySelector('.outline-slide-purpose-input');
        if (purposeInput) purposeInput.setAttribute('aria-label', `Slide ${position} purpose`);
        
        const removeBtn = item.querySelector('.outline-slide-remove-btn');
        if (removeBtn) {
            removeBtn.dataset.position = position;
            removeBtn.setAttribute('aria-label', `Remove slide ${position}`);
        }
    });
}

/**
 * Adds a new empty slide to the outline.
 */
export function addNewOutlineSlide() {
    const container = getById('outline-slides-editable');
    const currentCount = container ? container.children.length : 0;
    
    addOutlineSlideItem({
        topic: '',
        purpose: '',
        search_hints: []
    }, currentCount + 1);
}

/**
 * Gets the current outline data from the panel.
 * @returns {Object} The outline data
 */
export function getOutlineFromPanel() {
    const title = getById('outline-title-input')?.value || 'Presentation';
    const narrative = getById('outline-narrative-input')?.value || '';
    const slideItems = document.querySelectorAll('#outline-slides-editable .outline-slide-item');
    
    const slides = Array.from(slideItems).map((item, index) => ({
        position: index + 1,
        topic: item.querySelector('.outline-slide-topic-input')?.value || '',
        purpose: item.querySelector('.outline-slide-purpose-input')?.value || '',
        search_hints: JSON.parse(item.dataset.searchHints || '[]')
    }));
    
    return { title, narrative, slides };
}

/**
 * Resets the outline panel to its default state.
 */
export function resetOutlinePanel() {
    const outlinePanel = getById('outline-panel');
    if (!outlinePanel) return;
    
    // Restore original panel structure
    outlinePanel.innerHTML = `
        <div class="outline-panel-header">
            <div class="outline-panel-title">
                <span class="outline-icon">📋</span>
                <input type="text" class="outline-title-input" id="outline-title-input" placeholder="Presentation Title">
            </div>
            <div class="outline-panel-actions">
                <button class="outline-btn outline-confirm-btn" id="outline-confirm-btn">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                        <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                    Confirm & Build
                </button>
            </div>
        </div>
        <div class="outline-narrative-container">
            <label class="outline-label">Narrative</label>
            <textarea class="outline-narrative-input" id="outline-narrative-input" placeholder="Brief description of the presentation flow..."></textarea>
        </div>
        <div class="outline-slides-container">
            <label class="outline-label">Slides</label>
            <div class="outline-slides-list" id="outline-slides-editable"></div>
            <button class="outline-add-slide-btn" id="outline-add-slide-btn">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                    <line x1="12" y1="5" x2="12" y2="19"></line>
                    <line x1="5" y1="12" x2="19" y2="12"></line>
                </svg>
                Add Slide
            </button>
        </div>
    `;
    
    outlinePanel.style.display = 'none';
}
