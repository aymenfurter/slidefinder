/**
 * Agent Workflow Visualization
 * Displays AI agent progress and status.
 * @module components/deck-builder/agents
 */

'use strict';

import { escapeHtml, getById } from '../../utils/dom.js';

/** @type {HTMLElement|null} */
let currentAgentIndicator = null;

/** @type {Object|null} */
let currentOutline = null;

/**
 * Gets the icon for an agent type.
 * @param {string} agentName - The agent name
 * @returns {string} The emoji icon
 */
function getAgentIcon(agentName) {
    const icons = {
        researcher: '🔍',
        architect: '📐',
        author: '✍️',
        offer: '🎁',
        critic: '🎯',
        critique: '🎯'
    };
    return icons[agentName.toLowerCase()] || '🤖';
}

/**
 * Gets the color for an agent type.
 * @param {string} agentName - The agent name
 * @returns {string} The color hex code
 */
function getAgentColor(agentName) {
    const colors = {
        researcher: '#3b82f6',
        architect: '#8b5cf6',
        author: '#10b981',
        offer: '#06b6d4',
        critic: '#f59e0b',
        critique: '#f59e0b'
    };
    return colors[agentName.toLowerCase()] || '#6b7280';
}

/**
 * Adds an agent indicator to the chat.
 * @param {string} agentName - The agent name
 * @param {string} taskDescription - What the agent is doing
 * @param {Object} [details={}] - Additional details
 * @returns {HTMLElement|null} The indicator element
 */
export function addAgentIndicator(agentName, taskDescription, details = {}) {
    const messagesContainer = getById('chat-messages');
    if (!messagesContainer) return null;
    
    // Complete any existing agent indicator
    if (currentAgentIndicator) {
        completeAgentIndicator(currentAgentIndicator, true);
    }
    
    const indicator = document.createElement('div');
    indicator.className = 'agent-indicator';
    indicator.dataset.agent = agentName;
    
    const color = getAgentColor(agentName);
    const icon = getAgentIcon(agentName);
    
    let detailsHtml = '';
    if (details.round) {
        detailsHtml = `<span class="agent-detail">Round ${details.round}/5</span>`;
    } else if (details.revision_round !== undefined) {
        detailsHtml = `<span class="agent-detail">Revision ${details.revision_round}</span>`;
    }
    if (details.slides_so_far) {
        detailsHtml += `<span class="agent-detail">${details.slides_so_far} slides found</span>`;
    }
    
    indicator.innerHTML = `
        <div class="agent-icon" style="background: ${color}20; color: ${color}">${icon}</div>
        <div class="agent-info">
            <div class="agent-name" style="color: ${color}">${escapeHtml(agentName)}</div>
            <div class="agent-task">${escapeHtml(taskDescription)}</div>
            ${detailsHtml ? `<div class="agent-details">${detailsHtml}</div>` : ''}
        </div>
        <div class="agent-spinner">
            <div class="spinner-ring" style="border-color: ${color}40; border-top-color: ${color}"></div>
        </div>
    `;
    
    messagesContainer.appendChild(indicator);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    currentAgentIndicator = indicator;
    return indicator;
}

/**
 * Completes an agent indicator.
 * @param {HTMLElement} indicator - The indicator element
 * @param {boolean} [success=true] - Whether the agent succeeded
 * @param {string} [summary=''] - Optional summary text
 */
export function completeAgentIndicator(indicator, success = true, summary = '') {
    if (!indicator) return;
    
    indicator.classList.add('complete');
    
    const spinner = indicator.querySelector('.agent-spinner');
    if (spinner) {
        spinner.innerHTML = success 
            ? '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#10b981" stroke-width="2" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>'
            : '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#ef4444" stroke-width="2" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';
    }
    
    if (summary) {
        const taskEl = indicator.querySelector('.agent-task');
        if (taskEl) {
            taskEl.innerHTML = `<span class="agent-summary">${escapeHtml(summary)}</span>`;
        }
    }
    
    if (currentAgentIndicator === indicator) {
        currentAgentIndicator = null;
    }
}

/**
 * Gets the current agent indicator.
 * @returns {HTMLElement|null} The current indicator
 */
export function getCurrentAgentIndicator() {
    return currentAgentIndicator;
}

/**
 * Clears the current agent indicator reference.
 */
export function clearCurrentAgentIndicator() {
    currentAgentIndicator = null;
}

/**
 * Adds a search progress indicator.
 * @param {string} query - The search query
 * @param {number} resultCount - Number of results found
 * @param {number} [round] - The search round
 * @param {string} [reasoning] - The search reasoning
 */
export function addSearchProgressIndicator(query, resultCount, round, reasoning) {
    const activeIndicator = document.querySelector('.slide-selection-indicator.active');
    
    if (activeIndicator) {
        const critiqueLoop = activeIndicator.querySelector('.critique-loop');
        if (critiqueLoop) {
            const progressDiv = document.createElement('div');
            progressDiv.className = 'search-progress-indicator in-box';
            progressDiv.dataset.round = round || '1';
            
            progressDiv.innerHTML = `
                <div class="search-progress-icon">🔍</div>
                <div class="search-progress-info">
                    <div class="search-progress-query">"${escapeHtml(query)}"</div>
                    <div class="search-progress-result">Found ${resultCount} slides</div>
                </div>
            `;
            
            critiqueLoop.appendChild(progressDiv);
            
            const messagesContainer = getById('chat-messages');
            if (messagesContainer) {
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
            return;
        }
    }
    
    // Fallback: add standalone if no active slide box
    const messagesContainer = getById('chat-messages');
    if (!messagesContainer) return;
    
    const progressDiv = document.createElement('div');
    progressDiv.className = 'search-progress-indicator';
    
    progressDiv.innerHTML = `
        <div class="search-progress-icon">🔍</div>
        <div class="search-progress-info">
            <div class="search-progress-query">"${escapeHtml(query)}"</div>
            <div class="search-progress-result">Found ${resultCount} slides</div>
        </div>
    `;
    
    messagesContainer.appendChild(progressDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

/**
 * Adds revision feedback to the chat.
 * @param {number} revisionRound - The revision round number
 * @param {string} feedback - The feedback text
 * @param {Object} slideDecisions - Slide-by-slide decisions
 */
export function addRevisionFeedback(revisionRound, feedback, slideDecisions) {
    const messagesContainer = getById('chat-messages');
    if (!messagesContainer) return;
    
    const feedbackDiv = document.createElement('div');
    feedbackDiv.className = 'revision-feedback';
    
    let slideReviewHtml = '';
    if (slideDecisions && Object.keys(slideDecisions).length > 0) {
        const decisions = Object.entries(slideDecisions);
        const approved = decisions.filter(([_, d]) => d.status === 'approved');
        const toReplace = decisions.filter(([_, d]) => d.status === 'to-be-replaced');
        
        let reviewItems = '';
        
        toReplace.forEach(([key, decision]) => {
            reviewItems += `<li class="slide-decision replace">
                <span class="slide-status-icon">🔄</span>
                <span class="slide-key">Slide ${decision.slide_number || key}</span>
                <span class="slide-reason">${escapeHtml(decision.reason || 'Needs replacement')}</span>
            </li>`;
        });
        
        if (approved.length > 0) {
            reviewItems += `<li class="slide-decision approved">
                <span class="slide-status-icon">✓</span>
                <span class="slide-summary">${approved.length} slide${approved.length > 1 ? 's' : ''} approved</span>
            </li>`;
        }
        
        if (reviewItems) {
            slideReviewHtml = `
                <div class="slide-review-summary">
                    <strong>Slide Review:</strong>
                    <ul class="slide-decisions-list">${reviewItems}</ul>
                </div>
            `;
        }
    }
    
    feedbackDiv.innerHTML = `
        <div class="feedback-header">
            <span class="feedback-round">Revision ${revisionRound}</span>
            <span class="feedback-icon">📝</span>
        </div>
        <div class="feedback-content">${feedback ? escapeHtml(feedback) : 'Reviewing slides...'}</div>
        ${slideReviewHtml}
    `;
    
    messagesContainer.appendChild(feedbackDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

/**
 * Adds a slide selection indicator.
 * @param {number} position - The slide position
 * @param {string} topic - The slide topic
 * @param {number} total - Total number of slides
 * @returns {HTMLElement|null} The indicator element
 */
export function addSlideSelectionIndicator(position, topic, total) {
    const messagesContainer = getById('chat-messages');
    if (!messagesContainer) return null;
    
    const existing = document.querySelector('.slide-selection-indicator.active');
    if (existing) {
        existing.classList.remove('active');
        existing.classList.add('completed');
    }
    
    const indicator = document.createElement('div');
    indicator.className = 'slide-selection-indicator active';
    indicator.id = `slide-selection-${position}`;
    
    indicator.innerHTML = `
        <div class="selection-header">
            <span class="selection-position">Slide ${position}/${total}</span>
            <span class="selection-topic">${escapeHtml(topic)}</span>
        </div>
        <div class="selection-status">
            <div class="selection-spinner"></div>
            <span class="selection-status-text">Searching for best match...</span>
        </div>
        <div class="critique-loop" id="critique-loop-${position}"></div>
    `;
    
    messagesContainer.appendChild(indicator);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    return indicator;
}

/**
 * Updates the status text for a slide selection.
 * @param {number} position - The slide position
 * @param {string} status - The new status text
 */
export function updateSlideSelectionStatus(position, status) {
    const indicator = getById(`slide-selection-${position}`);
    if (!indicator) return;
    
    const statusText = indicator.querySelector('.selection-status-text');
    if (statusText) {
        statusText.textContent = status;
    }
}

/**
 * Adds a critique attempt to a slide selection.
 * @param {number} position - The slide position
 * @param {number} attempt - The attempt number
 * @param {Object} data - Critique data
 */
export function addCritiqueAttempt(position, attempt, data) {
    const critiqueLoop = getById(`critique-loop-${position}`);
    if (!critiqueLoop) return;
    
    critiqueLoop.innerHTML = '';
    updateSlideSelectionStatus(position, 'Evaluating slide...');
    
    const attemptDiv = document.createElement('div');
    attemptDiv.className = `critique-card ${data.approved ? 'approved' : 'rejected'}`;
    attemptDiv.dataset.attempt = attempt;
    
    const statusIcon = data.approved ? '✓' : '✗';
    const statusText = data.approved ? 'Approved' : 'Rejected';
    const thumbnailUrl = data.thumbnail_url || `/thumbnails/${data.slide_code}_${data.slide_number}.png`;
    
    attemptDiv.innerHTML = `
        <div class="critique-card-header">
            <div class="critique-search-info">
                <span class="critique-search-icon">🔍</span>
                <span class="critique-search-query">"${escapeHtml(data.search_query)}"</span>
                <span class="critique-result-count">${data.result_count} results</span>
            </div>
            <div class="critique-attempt-badge">Attempt ${attempt}</div>
        </div>
        <div class="critique-card-body">
            <div class="critique-thumbnail-wrapper">
                <img src="${thumbnailUrl}" alt="Slide preview" class="critique-thumbnail" onerror="this.parentElement.innerHTML='<div class=\\'critique-thumbnail-placeholder\\'>No preview</div>'" loading="lazy">
            </div>
            <div class="critique-details">
                <div class="critique-slide-info">
                    <span class="critique-slide-code">${escapeHtml(data.slide_code)}</span>
                    <span class="critique-slide-number">#${data.slide_number}</span>
                </div>
                ${data.slide_title ? `<div class="critique-slide-title">${escapeHtml(data.slide_title)}</div>` : ''}
                <div class="critique-verdict ${data.approved ? 'approved' : 'rejected'}">
                    <span class="verdict-icon">${statusIcon}</span>
                    <span class="verdict-text">${statusText}</span>
                </div>
                <div class="critique-feedback">${escapeHtml(data.feedback)}</div>
            </div>
        </div>
    `;
    
    critiqueLoop.appendChild(attemptDiv);
    
    const messagesContainer = getById('chat-messages');
    if (messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
}

/**
 * Adds an LLM judge indicator.
 * @param {number} position - The slide position
 * @param {number} candidateCount - Number of candidates being judged
 * @param {string} message - The judge message
 */
export function addLLMJudgeIndicator(position, candidateCount, message) {
    const critiqueLoop = getById(`critique-loop-${position}`);
    if (!critiqueLoop) return;
    
    critiqueLoop.innerHTML = '';
    
    const judgeDiv = document.createElement('div');
    judgeDiv.className = 'llm-judge-indicator';
    judgeDiv.innerHTML = `
        <div class="llm-judge-header">
            <span class="llm-judge-icon">⚖️</span>
            <span class="llm-judge-title">LLM Judge</span>
        </div>
        <div class="llm-judge-details">
            Evaluating ${candidateCount} candidate${candidateCount !== 1 ? 's' : ''} to find the best match.
        </div>
    `;
    
    critiqueLoop.appendChild(judgeDiv);
    
    const messagesContainer = getById('chat-messages');
    if (messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
}

/**
 * Completes a slide selection.
 * @param {number} position - The slide position
 * @param {Object} slide - The selected slide (null if not found)
 * @param {string} topic - The slide topic
 */
export function completeSlideSelection(position, slide, topic) {
    const indicator = getById(`slide-selection-${position}`);
    if (!indicator) return;
    
    indicator.classList.remove('active');
    indicator.classList.add('completed');
    
    const spinner = indicator.querySelector('.selection-spinner');
    if (spinner) {
        spinner.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#10b981" stroke-width="2" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>';
        spinner.classList.add('done');
    }
    
    const statusText = indicator.querySelector('.selection-status-text');
    if (statusText && slide) {
        statusText.textContent = `Selected: ${slide.session_code} #${slide.slide_number}`;
    } else if (statusText) {
        statusText.textContent = 'No suitable slide found';
    }
    
    // Update outline progress
    if (currentOutline) {
        const completed = document.querySelectorAll('.slide-selection-indicator.completed').length;
        updateOutlineProgress(completed, currentOutline.slideCount);
    }
}

/**
 * Marks a slide selection as failed.
 * @param {number} position - The slide position
 * @param {string} topic - The slide topic
 */
export function failSlideSelection(position, topic) {
    const indicator = getById(`slide-selection-${position}`);
    if (!indicator) return;
    
    indicator.classList.remove('active');
    indicator.classList.add('failed');
    
    const spinner = indicator.querySelector('.selection-spinner');
    if (spinner) {
        spinner.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#ef4444" stroke-width="2" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';
        spinner.classList.add('done');
    }
    
    const statusText = indicator.querySelector('.selection-status-text');
    if (statusText) {
        statusText.textContent = 'Could not find suitable slide';
    }
}

/**
 * Shows outline progress in the panel.
 * @param {string} title - Presentation title
 * @param {string} narrative - Presentation narrative
 * @param {number} slideCount - Total slide count
 */
export function showOutlineProgressPanel(title, narrative, slideCount) {
    const outlinePanel = getById('outline-panel');
    if (!outlinePanel) return;
    
    currentOutline = { title, narrative, slideCount };
    
    outlinePanel.innerHTML = `
        <div class="outline-progress-display" id="current-outline">
            <div class="outline-header">
                <span class="outline-icon">📋</span>
                <span class="outline-title">${escapeHtml(title)}</span>
            </div>
            <div class="outline-narrative">${escapeHtml(narrative)}</div>
            <div class="outline-progress">
                <div class="outline-progress-bar">
                    <div class="outline-progress-fill" style="width: 0%"></div>
                </div>
                <div class="outline-progress-text">0 / ${slideCount} slides</div>
            </div>
            <div class="outline-slides-list" id="outline-slides-list"></div>
        </div>
    `;
    
    outlinePanel.style.display = 'block';
}

/**
 * Updates the outline progress display.
 * @param {number} completed - Number of completed slides
 * @param {number} total - Total number of slides
 */
export function updateOutlineProgress(completed, total) {
    const progressBar = document.querySelector('.outline-progress-fill');
    const progressText = document.querySelector('.outline-progress-text');
    
    if (progressBar) {
        progressBar.style.width = `${(completed / total) * 100}%`;
    }
    if (progressText) {
        progressText.textContent = `${completed} / ${total} slides`;
    }
}

/**
 * Gets the current outline.
 * @returns {Object|null} The current outline
 */
export function getCurrentOutline() {
    return currentOutline;
}

/**
 * Sets the current outline.
 * @param {Object|null} outline - The outline
 */
export function setCurrentOutline(outline) {
    currentOutline = outline;
}
