/**
 * AI Overview Component
 * Displays an AI-generated overview at the top of search results.
 * @module components/ai-overview
 */

'use strict';

import { getById } from '../utils/dom.js';
import { fetchAIOverview } from '../services/api.js';

/** @type {AbortController|null} */
let currentOverviewRequest = null;

/**
 * Shows the AI overview container with loading state.
 */
export function showOverviewLoading() {
    const container = getById('ai-overview-container');
    if (!container) return;
    
    container.innerHTML = `
        <div class="ai-overview-box loading">
            <div class="ai-overview-header">
                <span class="ai-overview-icon">✨</span>
                <span class="ai-overview-label">AI Overview</span>
                <span class="ai-overview-spinner"></span>
            </div>
            <div class="ai-overview-content">
                <div class="ai-overview-skeleton">
                    <div class="skeleton-line"></div>
                    <div class="skeleton-line"></div>
                    <div class="skeleton-line short"></div>
                </div>
            </div>
        </div>
    `;
    container.classList.remove('hidden');
}

/**
 * Shows the AI overview with content.
 * @param {string} overview - The overview text (markdown)
 */
function showOverviewContent(overview) {
    const container = getById('ai-overview-container');
    if (!container) return;
    
    // Simple markdown to HTML conversion (bold only)
    const htmlContent = overview
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
    
    // Check if we're transitioning from loading state
    const existingBox = container.querySelector('.ai-overview-box');
    const isFromLoading = existingBox?.classList.contains('loading');
    
    if (isFromLoading) {
        // Smooth transition: update content in place with fade
        existingBox.classList.remove('loading');
        const contentDiv = existingBox.querySelector('.ai-overview-content');
        const spinner = existingBox.querySelector('.ai-overview-spinner');
        
        // Remove spinner
        if (spinner) spinner.remove();
        
        // Fade out skeleton, fade in content
        if (contentDiv) {
            contentDiv.classList.add('transitioning');
            contentDiv.innerHTML = `<p>${htmlContent}</p>`;
            // Force reflow then remove transitioning class
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    contentDiv.classList.remove('transitioning');
                });
            });
        }
    } else {
        // Fresh render
        container.innerHTML = `
            <div class="ai-overview-box">
                <div class="ai-overview-header">
                    <span class="ai-overview-icon">✨</span>
                    <span class="ai-overview-label">AI Overview</span>
                </div>
                <div class="ai-overview-content">
                    <p>${htmlContent}</p>
                </div>
            </div>
        `;
    }
    container.classList.remove('hidden');
}

/**
 * Hides the AI overview container.
 */
export function hideAIOverview() {
    const container = getById('ai-overview-container');
    if (container) {
        container.classList.add('hidden');
        container.innerHTML = '';
    }
    
    // Cancel any pending request
    if (currentOverviewRequest) {
        currentOverviewRequest.abort();
        currentOverviewRequest = null;
    }
}

/**
 * Fetches and displays an AI overview for search results.
 * @param {string} query - The search query
 * @param {string|null} searchContext - The search context JSON
 * @param {number} resultCount - Number of matching slides
 * @param {number} uniqueSessions - Number of unique sessions
 */
export async function loadAIOverview(query, searchContext, resultCount, uniqueSessions) {
    // Cancel any pending request
    if (currentOverviewRequest) {
        currentOverviewRequest.abort();
    }
    
    // Don't show overview if no context or few results
    if (!searchContext || resultCount < 3) {
        hideAIOverview();
        return;
    }
    
    // Show loading state
    showOverviewLoading();
    
    // Create abort controller for this request
    currentOverviewRequest = new AbortController();
    
    try {
        const response = await fetchAIOverview(
            query,
            searchContext,
            resultCount,
            uniqueSessions
        );
        
        if (response.available && response.overview) {
            showOverviewContent(response.overview);
        } else {
            hideAIOverview();
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            // Request was cancelled, do nothing
            return;
        }
        console.error('[AI Overview] Failed to load:', error);
        hideAIOverview();
    } finally {
        currentOverviewRequest = null;
    }
}
