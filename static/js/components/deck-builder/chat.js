/**
 * Chat Component
 * Handles chat messaging for the deck builder.
 * @module components/deck-builder/chat
 */

'use strict';

import { escapeHtml, formatMarkdown, getById } from '../../utils/dom.js';

/**
 * Adds a chat message to the messages container.
 * @param {string} content - The message content
 * @param {string} role - The message role ('user' or 'assistant')
 * @param {boolean} [isStreaming=false] - Whether to show typing indicator
 * @returns {HTMLElement|null} The bubble element (for streaming updates)
 */
export function addChatMessage(content, role, isStreaming = false) {
    const messagesContainer = getById('chat-messages');
    if (!messagesContainer) return null;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${role}`;
    
    const avatar = document.createElement('div');
    avatar.className = 'chat-avatar';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.textContent = role === 'user' ? '👤' : '🤖';
    
    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble';
    
    if (isStreaming) {
        bubble.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
    } else {
        bubble.innerHTML = formatMarkdown(content);
    }
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(bubble);
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    return bubble;
}

/**
 * Adds a tool call indicator to the chat.
 * @param {string} toolName - The tool being called
 * @param {Object} args - The tool arguments
 * @returns {HTMLElement} The indicator element
 */
export function addToolCallIndicator(toolName, args) {
    const messagesContainer = getById('chat-messages');
    if (!messagesContainer) return null;
    
    const indicator = document.createElement('div');
    indicator.className = 'tool-call-indicator';
    
    let icon = '🔧';
    let label = toolName;
    
    if (toolName === 'search_slides') {
        icon = '🔍';
        label = `Searching: "${escapeHtml(args.query || '')}"`;
        if (args.reason) {
            label += ` <span class="tool-reason">(${escapeHtml(args.reason)})</span>`;
        }
        indicator.classList.add('searching');
    } else if (toolName === 'compile_deck') {
        icon = '📊';
        label = `Compiling deck with ${args.slides?.length || 0} slides`;
    }
    
    indicator.innerHTML = `
        <div class="tool-icon">${icon}</div>
        <div class="tool-label">${label}</div>
        <div class="tool-spinner"></div>
    `;
    
    messagesContainer.appendChild(indicator);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    return indicator;
}

/**
 * Updates a tool call indicator to show completion.
 * @param {HTMLElement} indicator - The indicator element
 * @param {boolean} [success=true] - Whether the tool call succeeded
 */
export function updateToolCallIndicator(indicator, success = true) {
    if (!indicator) return;
    
    indicator.classList.remove('searching');
    
    const spinner = indicator.querySelector('.tool-spinner');
    if (spinner) {
        spinner.innerHTML = success 
            ? '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#10b981" stroke-width="2" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>'
            : '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#ef4444" stroke-width="2" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';
        spinner.classList.add('done');
    }
}

/**
 * Adds search results preview to the chat.
 * @param {Array} results - The search results
 */
export function addSearchResults(results) {
    const messagesContainer = getById('chat-messages');
    if (!messagesContainer || !results || results.length === 0) return;
    
    const resultsDiv = document.createElement('div');
    resultsDiv.className = 'search-results-preview';
    
    const previewSlides = results.slice(0, 4);
    
    resultsDiv.innerHTML = `
        <div class="search-results-header">Found ${results.length} slides</div>
        <div class="search-results-grid">
            ${previewSlides.map(slide => `
                <div class="search-result-card">
                    <img src="/thumbnails/${encodeURIComponent(slide.session_code)}_${slide.slide_number}.png" 
                         onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 16 9%22><rect fill=%22%23333%22 width=%2216%22 height=%229%22/></svg>'"
                         alt="${escapeHtml(slide.title)}"
                         loading="lazy">
                    <div class="search-result-info">
                        <span class="search-result-code">${escapeHtml(slide.session_code)}</span>
                        <span class="search-result-num">#${slide.slide_number}</span>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
    
    messagesContainer.appendChild(resultsDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

/**
 * Resets the chat to initial state.
 */
export function resetChat() {
    const messagesContainer = getById('chat-messages');
    if (!messagesContainer) return;
    
    messagesContainer.innerHTML = `
        <div class="chat-message assistant">
            <div class="chat-avatar" aria-hidden="true">🤖</div>
            <div class="chat-bubble">Hi! I'll help you build a custom slide deck from Microsoft Build and Ignite presentations.
<br>
<strong>How it works:</strong><br>
1. 🔍 I search for relevant slides<br>
2. 📐 I create an outline for your presentation<br>
3. 🎯 For each slide position, I find the best match and critique it<br>    
4. ✅ You get a polished deck!<br>
<br>
<strong>What topic would you like to create a presentation about?</strong></div>
        </div>
    `;
}

/**
 * Sets the processing state of chat input.
 * @param {boolean} isProcessing - Whether AI is processing
 */
export function setProcessingState(isProcessing) {
    const chatInput = getById('chat-input');
    const sendBtn = getById('chat-send-btn');
    
    if (chatInput) chatInput.disabled = isProcessing;
    if (sendBtn) sendBtn.disabled = isProcessing;
}

/**
 * Shows the "Create New Deck" option after deck is complete.
 */
export function showNewDeckOption() {
    const chatInputArea = getById('chat-input-area');
    const newDeckArea = getById('chat-new-deck-area');
    
    if (chatInputArea) chatInputArea.style.display = 'none';
    if (newDeckArea) newDeckArea.style.display = 'flex';
}

/**
 * Hides the "Create New Deck" option and shows chat input.
 */
export function hideNewDeckOption() {
    const newDeckArea = getById('chat-new-deck-area');
    const chatInputArea = getById('chat-input-area');
    
    if (newDeckArea) newDeckArea.style.display = 'none';
    if (chatInputArea) chatInputArea.style.display = '';
}
