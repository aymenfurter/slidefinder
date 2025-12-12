/**
 * API Service Module
 * Handles all HTTP communication with the backend.
 * @module services/api
 */

'use strict';

import { updateCache, getFromCache, hasInCache } from '../state/store.js';

/** Base API URL (relative to origin) */
const API_BASE = '/api';

/** Session ID pattern for detection */
const SESSION_ID_PATTERN = /^([A-Za-z]{2,4}\d{2,4})$/;

/**
 * Checks if a query looks like a session ID.
 * @param {string} query - The query to check
 * @returns {boolean} True if it matches session ID pattern
 */
export function isSessionId(query) {
    return SESSION_ID_PATTERN.test(query?.trim() || '');
}

/**
 * Makes a fetch request with standard error handling.
 * @param {string} url - The URL to fetch
 * @param {RequestInit} [options={}] - Fetch options
 * @returns {Promise<Response>} The fetch response
 * @throws {Error} If the request fails
 */
async function fetchWithErrorHandling(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        }
    });
    
    if (!response.ok) {
        const errorText = await response.text().catch(() => 'Unknown error');
        throw new Error(`HTTP ${response.status}: ${errorText}`);
    }
    
    return response;
}

/**
 * Fetches search results for a query.
 * Results are cached to avoid redundant requests.
 * @param {string} query - The search query
 * @returns {Promise<Object>} The search results
 */
export async function fetchSearchResults(query) {
    if (hasInCache(query)) {
        return getFromCache(query);
    }
    
    const response = await fetchWithErrorHandling(
        `${API_BASE}/search?q=${encodeURIComponent(query)}`
    );
    const data = await response.json();
    
    updateCache(query, data);
    return data;
}

/**
 * Fetches all slides for a specific session.
 * @param {string} sessionCode - The session code (e.g., 'BRK108')
 * @returns {Promise<Object>} The session slides data
 */
export async function fetchSessionSlides(sessionCode) {
    const cacheKey = `session:${sessionCode.toUpperCase()}`;
    
    if (hasInCache(cacheKey)) {
        return getFromCache(cacheKey);
    }
    
    const response = await fetchWithErrorHandling(
        `${API_BASE}/session/${encodeURIComponent(sessionCode)}`
    );
    const data = await response.json();
    
    updateCache(cacheKey, data);
    return data;
}

/**
 * Sends a message to the deck builder chat endpoint.
 * Returns a readable stream for SSE processing.
 * @param {string} message - The user message
 * @param {string|null} sessionId - The session ID (null for new session)
 * @returns {Promise<ReadableStream>} The response body stream
 */
export async function sendDeckBuilderMessage(message, sessionId) {
    const response = await fetch(`${API_BASE}/deck-builder/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message: message,
            session_id: sessionId
        })
    });
    
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: Failed to send message`);
    }
    
    return response.body;
}

/**
 * Confirms an outline and continues deck building.
 * Returns a readable stream for SSE processing.
 * @param {string} sessionId - The session ID
 * @param {Object} outline - The outline data
 * @param {string} outline.title - Presentation title
 * @param {string} outline.narrative - Presentation narrative
 * @param {Array} outline.slides - Slide definitions
 * @param {Array} allSlides - All available slides for the outline
 * @returns {Promise<ReadableStream>} The response body stream
 */
export async function confirmOutline(sessionId, outline, allSlides) {
    const response = await fetch(`${API_BASE}/deck-builder/confirm-outline/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            session_id: sessionId,
            title: outline.title,
            narrative: outline.narrative,
            slides: outline.slides,
            all_slides: allSlides
        })
    });
    
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: Failed to confirm outline`);
    }
    
    return response.body;
}

/**
 * Gets the download URL for a deck.
 * @param {string} sessionId - The session ID
 * @returns {string} The download URL
 */
export function getDeckDownloadUrl(sessionId) {
    return `${API_BASE}/deck-builder/download/${sessionId}`;
}

/**
 * Gets the thumbnail URL for a slide.
 * @param {string} sessionCode - The session code
 * @param {number} slideNumber - The slide number
 * @returns {string} The thumbnail URL
 */
export function getThumbnailUrl(sessionCode, slideNumber) {
    return `/thumbnails/${sessionCode}_${slideNumber}.png`;
}

/**
 * Fetches an AI overview for search results.
 * @param {string} query - The search query
 * @param {string} searchContext - The search context JSON from search results
 * @param {number} resultCount - Number of matching slides
 * @param {number} uniqueSessions - Number of unique presentation sessions
 * @returns {Promise<Object>} The AI overview response
 */
export async function fetchAIOverview(query, searchContext, resultCount, uniqueSessions) {
    const response = await fetchWithErrorHandling(`${API_BASE}/ai-overview`, {
        method: 'POST',
        body: JSON.stringify({
            query: query,
            search_context: searchContext,
            result_count: resultCount,
            unique_sessions: uniqueSessions
        })
    });
    return response.json();
}

/**
 * Fetches an AI overview with streaming response.
 * @param {string} query - The search query
 * @param {string} searchContext - The search context JSON from search results
 * @param {number} resultCount - Number of matching slides
 * @param {number} uniqueSessions - Number of unique presentation sessions
 * @returns {Promise<ReadableStream>} The response body stream
 */
export async function fetchAIOverviewStream(query, searchContext, resultCount, uniqueSessions) {
    const response = await fetch(`${API_BASE}/ai-overview/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            query: query,
            search_context: searchContext,
            result_count: resultCount,
            unique_sessions: uniqueSessions
        })
    });
    
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: Failed to fetch AI overview`);
    }
    
    return response.body;
}

/**
 * Parses an SSE stream and yields events.
 * @param {ReadableStream} stream - The response body stream
 * @yields {Object} Parsed SSE event data
 */
export async function* parseSSEStream(stream) {
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let currentEventType = null;
    
    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            
            for (const line of lines) {
                if (line.startsWith('event:')) {
                    currentEventType = line.slice(6).trim();
                    continue;
                }
                
                if (line.startsWith('data:')) {
                    try {
                        const jsonStr = line.startsWith('data: ') ? line.slice(6) : line.slice(5);
                        const data = JSON.parse(jsonStr);
                        
                        // Use event type from SSE header if data.type is not set
                        if (currentEventType && !data.type) {
                            data.type = currentEventType;
                        }
                        currentEventType = null;
                        
                        yield data;
                    } catch (e) {
                        console.warn('[API] Failed to parse SSE data:', e.message);
                    }
                }
            }
        }
    } finally {
        reader.releaseLock();
    }
}

// Export as default object for convenient importing
const api = {
    isSessionId,
    fetchSearchResults,
    fetchSessionSlides,
    sendDeckBuilderMessage,
    confirmOutline,
    getDeckDownloadUrl,
    getThumbnailUrl,
    fetchAIOverview,
    fetchAIOverviewStream,
    parseSSEStream
};

export default api;
