/**
 * Slide Assistant Component - AI-powered chat for finding slides.
 * @module components/slide-assistant
 */

'use strict';

import { getById, createElement, formatMarkdown } from '../utils/dom.js';
import { parseSSEStream } from '../services/api.js';

const ASSISTANT_LOGO = '<img src="/static/favicon/favicon.svg" alt="" width="20" height="20">';
const USER_AVATAR = '👤';

let chatHistory = [];
let isProcessing = false;

/** Toggle the slide assistant panel visibility. */
export function toggleSlideAssistant() {
    const section = getById('slide-assistant-section');
    const toggleBtn = getById('slide-assistant-toggle');
    if (!section) return;
    
    const isVisible = section.classList.toggle('visible');
    toggleBtn?.classList.toggle('active', isVisible);
    document.body.classList.toggle('assistant-open', isVisible);
    
    // Reset zoom when closing
    if (!isVisible) {
        section.classList.remove('zoomed');
        document.body.classList.remove('assistant-zoomed');
    }
    
    if (isVisible) setTimeout(() => getById('assistant-input')?.focus(), 100);
}

/** Toggle zoom (full width) mode for the assistant. */
export function toggleAssistantZoom() {
    const section = getById('slide-assistant-section');
    if (!section) return;
    
    const isZoomed = section.classList.toggle('zoomed');
    document.body.classList.toggle('assistant-zoomed', isZoomed);
}

/** Send a message to the slide assistant. */
export async function sendAssistantMessage() {
    const input = getById('assistant-input');
    const message = input?.value?.trim();
    if (!message || isProcessing) return;
    
    isProcessing = true;
    setInputEnabled(false);
    addMessage('user', message);
    input.value = '';
    
    // Send history WITHOUT current message (it's sent separately as 'message')
    const historyToSend = chatHistory.slice(-6);
    chatHistory.push({ role: 'user', content: message });
    
    const typingId = showTyping();
    
    try {
        const response = await fetch('/api/slide-assistant/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, history: historyToSend }),
        });
        
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        for await (const event of parseSSEStream(response.body)) {
            if (event.type === 'status') updateTyping(typingId, event.message);
            else if (event.type === 'response') {
                removeTyping(typingId);
                addResponse(event.answer, event.referenced_slides, event.follow_up_suggestions);
                chatHistory.push({ role: 'assistant', content: event.answer });
            } else if (event.type === 'error') {
                removeTyping(typingId);
                addMessage('assistant', `Error: ${event.message}`);
            } else if (event.type === 'done') {
                removeTyping(typingId);
            }
        }
    } catch (error) {
        console.error('[SlideAssistant]', error);
        removeTyping(typingId);
        addMessage('assistant', 'An error occurred. Please try again.');
    } finally {
        isProcessing = false;
        setInputEnabled(true);
    }
}

/** Add a simple message to the chat. */
function addMessage(role, content) {
    const container = getById('assistant-messages');
    if (!container) return;
    
    const msg = createElement('div', { className: `assistant-message ${role}` });
    const avatar = createElement('div', { className: 'assistant-avatar' });
    avatar.innerHTML = role === 'user' ? USER_AVATAR : ASSISTANT_LOGO;
    msg.appendChild(avatar);
    
    const bubble = createElement('div', { className: 'assistant-bubble' });
    bubble.innerHTML = formatMarkdown(content);
    msg.appendChild(bubble);
    
    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
}

/** Add assistant response with slides. */
function addResponse(answer, slides, suggestions) {
    const container = getById('assistant-messages');
    if (!container) return;
    
    const msg = createElement('div', { className: 'assistant-message assistant' });
    const avatar = createElement('div', { className: 'assistant-avatar' });
    avatar.innerHTML = ASSISTANT_LOGO;
    msg.appendChild(avatar);
    
    const bubble = createElement('div', { className: 'assistant-bubble' });
    
    // Answer
    const answerDiv = createElement('div', { className: 'assistant-answer' });
    answerDiv.innerHTML = formatMarkdown(answer);
    bubble.appendChild(answerDiv);
    
    // Slides
    if (slides?.length) {
        const slidesDiv = createElement('div', { className: 'assistant-slides' });
        slidesDiv.appendChild(createElement('div', { className: 'assistant-slides-label' }, `📌 Referenced Slides (${slides.length})`));
        
        const grid = createElement('div', { className: 'assistant-slides-grid' });
        slides.forEach(slide => grid.appendChild(createSlideCard(slide)));
        slidesDiv.appendChild(grid);
        bubble.appendChild(slidesDiv);
    }
    
    // Suggestions
    if (suggestions?.length) {
        const sugDiv = createElement('div', { className: 'assistant-suggestions' });
        suggestions.forEach(s => {
            const btn = createElement('button', { className: 'assistant-suggestion-btn' }, s);
            btn.onclick = () => { getById('assistant-input').value = s; sendAssistantMessage(); };
            sugDiv.appendChild(btn);
        });
        bubble.appendChild(sugDiv);
    }
    
    msg.appendChild(bubble);
    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
}

/** Create a slide card element. */
function createSlideCard(slide) {
    const card = createElement('div', { className: 'assistant-slide-card' });
    
    // Thumbnail
    const thumb = createElement('div', { className: 'assistant-slide-thumb' });
    if (slide.thumbnail_url) {
        const img = createElement('img', { src: slide.thumbnail_url, alt: `Slide ${slide.slide_number}`, loading: 'lazy' });
        img.onerror = () => { thumb.innerHTML = '<div class="assistant-slide-placeholder">📄</div>'; };
        thumb.appendChild(img);
    } else {
        thumb.innerHTML = '<div class="assistant-slide-placeholder">📄</div>';
    }
    card.appendChild(thumb);
    
    // Info
    const info = createElement('div', { className: 'assistant-slide-info' });
    
    const header = createElement('div', { className: 'assistant-slide-header' });
    header.appendChild(createElement('span', { className: `assistant-slide-badge ${slide.event?.toLowerCase() || ''}` }, slide.session_code));
    header.appendChild(createElement('span', { className: 'assistant-slide-num' }, `#${slide.slide_number}`));
    info.appendChild(header);
    
    if (slide.title) {
        const title = slide.title.length > 60 ? slide.title.slice(0, 60) + '...' : slide.title;
        info.appendChild(createElement('div', { className: 'assistant-slide-title', title: slide.title }, title));
    }
    
    if (slide.relevance_reason) {
        info.appendChild(createElement('div', { className: 'assistant-slide-reason' }, slide.relevance_reason));
    }
    
    // Action buttons (Watch & Open)
    const actions = createElement('div', { className: 'assistant-slide-actions' });
    
    if (slide.session_url) {
        const watchBtn = createElement('a', { 
            className: 'assistant-action-btn', 
            href: slide.session_url, 
            target: '_blank', 
            rel: 'noopener noreferrer' 
        });
        watchBtn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Watch`;
        actions.appendChild(watchBtn);
    }
    
    if (slide.ppt_url) {
        const openBtn = createElement('a', { 
            className: 'assistant-action-btn', 
            href: slide.ppt_url, 
            target: '_blank', 
            rel: 'noopener noreferrer' 
        });
        openBtn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg> Open`;
        actions.appendChild(openBtn);
    }
    
    if (actions.children.length > 0) {
        info.appendChild(actions);
    }
    
    card.appendChild(info);
    return card;
}

/** Show typing indicator. */
function showTyping() {
    const container = getById('assistant-messages');
    if (!container) return '';
    
    const id = `typing-${Date.now()}`;
    const indicator = createElement('div', { className: 'assistant-message assistant typing-message', id });
    const avatar = createElement('div', { className: 'assistant-avatar' });
    avatar.innerHTML = ASSISTANT_LOGO;
    indicator.appendChild(avatar);
    
    const bubble = createElement('div', { className: 'assistant-bubble' });
    bubble.innerHTML = '<div class="assistant-typing"><span class="typing-status">Thinking...</span><div class="typing-dots"><span></span><span></span><span></span></div></div>';
    indicator.appendChild(bubble);
    
    container.appendChild(indicator);
    container.scrollTop = container.scrollHeight;
    return id;
}

function updateTyping(id, message) {
    const status = getById(id)?.querySelector('.typing-status');
    if (status) status.textContent = message;
}

function removeTyping(id) {
    getById(id)?.remove();
}

function setInputEnabled(enabled) {
    const input = getById('assistant-input');
    const btn = getById('assistant-send-btn');
    if (input) input.disabled = !enabled;
    if (btn) btn.disabled = !enabled;
}

/** Clear chat history and UI. */
export function clearAssistantChat() {
    chatHistory = [];
    const container = getById('assistant-messages');
    if (container) {
        container.innerHTML = `
            <div class="assistant-message assistant">
                <div class="assistant-avatar"><img src="/static/favicon/favicon.svg" alt="" width="20" height="20"></div>
                <div class="assistant-bubble">
                    <p>Hi! I'm your slide assistant. Ask me to help find slides from Microsoft Build and Ignite.</p>
                    <p><strong>Try:</strong></p>
                    <ul class="assistant-examples">
                        <li class="assistant-example-btn" data-query="Find slides about Azure Kubernetes Service">Find slides about Azure Kubernetes Service</li>
                        <li class="assistant-example-btn" data-query="Show me slides on GitHub Copilot">Show me slides on GitHub Copilot</li>
                        <li class="assistant-example-btn" data-query="What slides cover AI agents?">What slides cover AI agents?</li>
                    </ul>
                    <p class="assistant-disclaimer">AI can make mistakes. Verify important information.</p>
                </div>
            </div>`;
        setupExampleListeners();
    }
}

function setupExampleListeners() {
    document.querySelectorAll('.assistant-example-btn').forEach(btn => {
        btn.onclick = () => {
            if (!isProcessing) {
                getById('assistant-input').value = btn.dataset.query;
                sendAssistantMessage();
            }
        };
    });
}

/** Initialize the slide assistant. */
export function initSlideAssistant() {
    getById('assistant-input')?.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendAssistantMessage(); }
    });
    getById('assistant-send-btn')?.addEventListener('click', sendAssistantMessage);
    getById('assistant-clear-btn')?.addEventListener('click', clearAssistantChat);
    getById('slide-assistant-toggle')?.addEventListener('click', toggleSlideAssistant);
    getById('assistant-close-btn')?.addEventListener('click', toggleSlideAssistant);
    getById('assistant-zoom-btn')?.addEventListener('click', toggleAssistantZoom);
    setupExampleListeners();
}

export default { toggleSlideAssistant, toggleAssistantZoom, sendAssistantMessage, clearAssistantChat, initSlideAssistant };
