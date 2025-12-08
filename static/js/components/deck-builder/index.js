/**
 * Deck Builder Main Module
 * Orchestrates the deck builder functionality.
 * @module components/deck-builder/index
 */

'use strict';

import { getById } from '../../utils/dom.js';
import { showToast } from '../../utils/toast.js';
import { get, setState, resetDeckBuilder } from '../../state/store.js';
import { sendDeckBuilderMessage, confirmOutline, getDeckDownloadUrl, parseSSEStream } from '../../services/api.js';

import {
    addChatMessage,
    addToolCallIndicator,
    updateToolCallIndicator,
    addSearchResults,
    resetChat,
    setProcessingState,
    showNewDeckOption,
    hideNewDeckOption
} from './chat.js';

import {
    addAgentIndicator,
    completeAgentIndicator,
    getCurrentAgentIndicator,
    addSearchProgressIndicator,
    addRevisionFeedback,
    addSlideSelectionIndicator,
    addCritiqueAttempt,
    addLLMJudgeIndicator,
    completeSlideSelection,
    failSlideSelection,
    showOutlineProgressPanel,
    setCurrentOutline
} from './agents.js';

import {
    showOutlinePanel,
    hideOutlinePanel,
    getOutlineFromPanel,
    addNewOutlineSlide,
    resetOutlinePanel
} from './outline.js';

import {
    updateDeckPreview,
    updateSourceDecks,
    switchPreviewTab,
    switchViewMode,
    updateIntermediateDeck
} from './preview.js';

/**
 * Shows the deck builder section.
 */
export function showDeckBuilder() {
    const deckSection = getById('deck-builder-section');
    const mainContent = getById('main-content');
    const heroEl = getById('hero');
    const deckBtn = getById('deckbuilder-toggle');
    
    if (deckSection) deckSection.style.display = 'block';
    if (mainContent) mainContent.classList.add('hidden');
    if (heroEl) heroEl.style.display = 'none';
    if (deckBtn) deckBtn.classList.add('active');
}

/**
 * Toggles the deck builder visibility.
 */
export function toggleDeckBuilder() {
    const deckSection = getById('deck-builder-section');
    const mainContent = getById('main-content');
    const favSection = getById('favorites-section');
    const heroEl = getById('hero');
    const deckBtn = getById('deckbuilder-toggle');
    const favBtn = getById('favorites-toggle');
    
    const isVisible = deckSection && window.getComputedStyle(deckSection).display !== 'none';
    
    if (isVisible) {
        if (deckSection) deckSection.style.display = 'none';
        if (mainContent) mainContent.classList.remove('hidden');
        if (heroEl) heroEl.style.display = '';
        if (deckBtn) deckBtn.classList.remove('active');
    } else {
        if (deckSection) deckSection.style.display = 'block';
        if (mainContent) mainContent.classList.add('hidden');
        if (favSection) favSection.classList.remove('visible');
        if (heroEl) heroEl.style.display = 'none';
        if (deckBtn) deckBtn.classList.add('active');
        if (favBtn) favBtn.classList.remove('active');
        setState({ showingFavorites: false });
    }
}

/**
 * Starts a new deck session.
 */
export function startNewDeck() {
    resetDeckBuilder();
    setCurrentOutline(null);
    
    hideOutlinePanel();
    hideNewDeckOption();
    resetOutlinePanel();
    
    const chatInputArea = getById('chat-input-area');
    if (chatInputArea) {
        chatInputArea.style.display = '';
    }
    
    resetChat();
    updateDeckPreview([]);
    updateSourceDecks([]);
    switchPreviewTab('preview');
}

/**
 * Handles SSE events from the deck builder.
 * @param {Object} data - The event data
 * @param {Object} context - Processing context
 */
function handleSSEEvent(data, context) {
    switch (data.type) {
        case 'session':
            setState({ deckSessionId: data.session_id });
            console.log('[SSE] Session ID captured:', data.session_id);
            break;
            
        case 'thinking':
            if (context.assistantBubble) {
                context.assistantBubble.innerHTML = `<em>${data.message}</em>`;
            }
            break;
        
        case 'agent_start':
            addAgentIndicator(data.agent, data.task, data.details);
            break;
            
        case 'agent_complete':
            const currentAgent = getCurrentAgentIndicator();
            if (currentAgent) {
                completeAgentIndicator(currentAgent, true, data.summary);
            }
            break;
        
        case 'outline_pending':
            setState({
                pendingOutline: {
                    title: data.title,
                    narrative: data.narrative,
                    slides: data.slides
                },
                allSlidesForOutline: data.all_slides,
                outlineConfirmed: false
            });
            showOutlinePanel(data.title, data.narrative, data.slides);
            break;
        
        case 'awaiting_confirmation':
            setProcessingState(false);
            break;
        
        case 'outline_created':
            // Legacy event - handled by outline_pending now
            break;
        
        case 'slide_selection_start':
            addSlideSelectionIndicator(data.position, data.topic, data.total);
            break;
        
        case 'slide_selected':
            completeSlideSelection(data.position, data.slide, data.topic);
            break;
        
        case 'slide_not_found':
            failSlideSelection(data.position, data.topic);
            break;
        
        case 'critique_attempt':
            addCritiqueAttempt(data.position, data.attempt, {
                search_query: data.search_query,
                result_count: data.result_count,
                slide_code: data.slide_code,
                slide_number: data.slide_number,
                slide_title: data.slide_title,
                selection_reason: data.selection_reason,
                approved: data.approved,
                feedback: data.feedback,
                issues: data.issues
            });
            break;
            
        case 'llm_judge_start':
            addLLMJudgeIndicator(data.position, data.candidate_count, data.message);
            break;
            
        case 'intermediate_deck':
            updateIntermediateDeck(data.deck, data.narrative, data.revision_round, data.is_final);
            break;
            
        case 'revision_progress':
            if (data.slide_decisions) {
                setState({ slideReviews: data.slide_decisions });
                const deckSlides = get('deckSlides');
                if (deckSlides && deckSlides.length > 0) {
                    updateDeckPreview(deckSlides, true);
                }
            }
            addRevisionFeedback(data.revision_round, data.feedback, data.slide_decisions);
            break;
            
        case 'narrative_update':
            console.log('[SSE] Narrative updated:', data.narrative?.substring(0, 100));
            break;
            
        case 'tool_call':
            if (context.currentToolIndicator) {
                updateToolCallIndicator(context.currentToolIndicator, true);
            }
            context.currentToolIndicator = addToolCallIndicator(data.tool, data.args);
            break;
            
        case 'search_complete':
            if (context.currentToolIndicator) {
                updateToolCallIndicator(context.currentToolIndicator, true);
                context.currentToolIndicator = null;
            }
            addSearchResults(data.results);
            break;
            
        case 'deck_compiled':
            if (context.currentToolIndicator) {
                updateToolCallIndicator(context.currentToolIndicator, true);
                context.currentToolIndicator = null;
            }
            const currentAgentInd = getCurrentAgentIndicator();
            if (currentAgentInd) {
                completeAgentIndicator(currentAgentInd, true);
            }
            
            setState({ slideReviews: {} });
            updateDeckPreview(data.slides, true);
            
            if (get('outlineConfirmed')) {
                showNewDeckOption();
            }
            break;
            
        case 'message':
            context.fullResponse = data.content;
            break;
            
        case 'download_info':
            updateSourceDecks(data.decks);
            const downloadBtn = getById('download-pptx-btn');
            if (downloadBtn) downloadBtn.style.display = 'flex';
            break;
            
        case 'complete':
            if (context.currentToolIndicator) {
                updateToolCallIndicator(context.currentToolIndicator, true);
            }
            const agentInd = getCurrentAgentIndicator();
            if (agentInd) {
                completeAgentIndicator(agentInd, true);
            }
            if (context.fullResponse && context.fullResponse.trim() && !context.fullResponse.trim().startsWith('assistant')) {
                addChatMessage(context.fullResponse, 'assistant', false);
            }
            if (get('outlineConfirmed')) {
                showNewDeckOption();
            }
            break;
            
        case 'error':
            const errorAgent = getCurrentAgentIndicator();
            if (errorAgent) {
                completeAgentIndicator(errorAgent, false);
            }
            addChatMessage(`Error: ${data.message}`, 'assistant', false);
            break;
    }
}

/**
 * Sends a chat message and processes the response.
 */
export async function sendChatMessage() {
    const input = getById('chat-input');
    
    if (!input) return;
    
    const message = input.value.trim();
    if (!message || get('isAiProcessing')) return;
    
    input.value = '';
    setState({ isAiProcessing: true });
    setProcessingState(true);
    
    addChatMessage(message, 'user');
    
    const context = {
        assistantBubble: null,
        currentToolIndicator: null,
        fullResponse: ''
    };
    
    try {
        const sessionId = get('deckSessionId');
        console.log('[SSE] Sending message with session_id:', sessionId);
        
        const stream = await sendDeckBuilderMessage(message, sessionId);
        
        for await (const data of parseSSEStream(stream)) {
            handleSSEEvent(data, context);
        }
        
    } catch (error) {
        console.error('Chat error:', error);
        addChatMessage(`Error: ${error.message}`, 'assistant', false);
    } finally {
        setState({ isAiProcessing: false });
        setProcessingState(false);
        input.focus();
    }
}

/**
 * Confirms the outline and continues building.
 */
export async function confirmOutlineAndContinue() {
    const pendingOutline = get('pendingOutline');
    const allSlidesForOutline = get('allSlidesForOutline');
    
    if (!pendingOutline || !allSlidesForOutline) {
        console.error('No pending outline to confirm');
        return;
    }
    
    const confirmBtn = getById('outline-confirm-btn');
    if (confirmBtn) {
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<span class="selection-spinner" style="width:14px;height:14px;"></span> Building...';
    }
    
    const editedOutline = getOutlineFromPanel();
    setState({ outlineConfirmed: true });
    
    showOutlineProgressPanel(editedOutline.title, editedOutline.narrative, editedOutline.slides.length);
    
    const context = {
        assistantBubble: null,
        currentToolIndicator: null,
        fullResponse: ''
    };
    
    try {
        const sessionId = get('deckSessionId');
        const stream = await confirmOutline(sessionId, editedOutline, allSlidesForOutline);
        
        for await (const data of parseSSEStream(stream)) {
            handleSSEEvent(data, context);
        }
        
    } catch (error) {
        console.error('Error confirming outline:', error);
        addChatMessage('Sorry, there was an error building the deck. Please try again.', 'assistant');
    }
    
    setState({ isAiProcessing: false });
}

/**
 * Downloads the current deck as PPTX.
 */
export function downloadDeck() {
    const sessionId = get('deckSessionId');
    
    if (!sessionId) {
        showToast('No active session to download.');
        return;
    }
    
    const downloadUrl = getDeckDownloadUrl(sessionId);
    
    // Create a temporary link for download
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = downloadUrl;
    a.download = `slidefinder_deck_${sessionId}.pptx`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    
    showToast('Download started...');
}

/**
 * Downloads the current deck data as CSV.
 */
export function downloadDeckAsCSV() {
    const deckSlides = get('deckSlides');
    const deckSources = get('deckSources');
    
    if (!deckSlides || deckSlides.length === 0) {
        showToast('No deck data to download.');
        return;
    }
    
    // Build CSV content
    const headers = ['Position', 'Session Code', 'Slide Number', 'Title', 'Reason', 'Source URL'];
    const rows = deckSlides.map((slide, idx) => {
        const source = deckSources?.find(s => s.session_code === slide.session_code);
        return [
            idx + 1,
            slide.session_code || '',
            slide.slide_number || '',
            slide.title || '',
            slide.reason || '',
            source?.ppt_url || ''
        ];
    });
    
    // Escape CSV values
    const escapeCSV = (val) => {
        const str = String(val);
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
            return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
    };
    
    const csvContent = [
        headers.map(escapeCSV).join(','),
        ...rows.map(row => row.map(escapeCSV).join(','))
    ].join('\n');
    
    // Create and trigger download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = `slidefinder_deck_${new Date().toISOString().slice(0,10)}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showToast('CSV downloaded!');
}

// Re-export sub-module functions for external use
export {
    switchPreviewTab,
    switchViewMode,
    addNewOutlineSlide
};
