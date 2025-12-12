/**
 * Nerd Info Panel Component
 * Shows detailed debug information about the AI workflow.
 * 
 * Features:
 * - Fixed workflow graph visualization at top
 * - Filter events by workflow stage
 * - Slide thumbnail previews
 * - GitHub code links for learning how the workflow is implemented
 * 
 * Backend always emits debug_* events - this module decides whether to display them.
 * Integrated as a tab in the chat panel.
 * @module components/deck-builder/nerd-info
 */

'use strict';

import { escapeHtml, getById } from '../../utils/dom.js';

/** @type {boolean} - Whether the nerd info tab is currently active */
let nerdTabActive = false;

/** @type {Array<Object>} */
let workflowEvents = [];

/** @type {number} */
let eventCounter = 0;

/** @type {string|null} - Current filter (null = all, or 'outline', 'search', 'offer', 'critique', 'judge', or 'slide-X') */
let currentFilter = null;

/** @type {string} - Current phase: 'idle', 'outline', 'slides' */
let currentPhase = 'idle';

/** @type {string} - Current active executor/stage in the workflow */
let currentStage = 'idle';

/** @type {number} - Current slide position being processed */
let currentSlidePosition = 0;

/** @type {number} - Total slides to process */
let totalSlides = 0;

/** @type {Object} - Track slides and their iterations */
let slideWorkflows = {};

/** GitHub repo base URL for code links */
const GITHUB_REPO = 'https://github.com/aymenfurter/slidefinder/blob/main';

/**
 * Initializes the nerd info panel and tab switching.
 */
export function initNerdInfo() {
    // Set up tab click handlers
    const chatTab = getById('chat-tab');
    const nerdTab = getById('nerd-tab');
    
    if (chatTab) {
        chatTab.addEventListener('click', () => switchToTab('chat'));
    }
    if (nerdTab) {
        nerdTab.addEventListener('click', () => switchToTab('nerd'));
    }
}

/**
 * Switches between chat and nerd info tabs.
 * @param {string} tab - 'chat' or 'nerd'
 */
export function switchToTab(tab) {
    const chatTab = getById('chat-tab');
    const nerdTab = getById('nerd-tab');
    const chatMessages = getById('chat-messages');
    const chatInputArea = getById('chat-input-area');
    const chatNewDeckArea = getById('chat-new-deck-area');
    const nerdContent = getById('nerd-info-content');
    
    nerdTabActive = (tab === 'nerd');
    
    // Update tab active states
    if (chatTab) {
        chatTab.classList.toggle('active', tab === 'chat');
        chatTab.setAttribute('aria-selected', tab === 'chat');
    }
    if (nerdTab) {
        nerdTab.classList.toggle('active', tab === 'nerd');
        nerdTab.setAttribute('aria-selected', tab === 'nerd');
    }
    
    // Show/hide content areas
    if (chatMessages) {
        chatMessages.style.display = tab === 'chat' ? 'flex' : 'none';
    }
    if (chatInputArea) {
        chatInputArea.style.display = tab === 'chat' ? 'block' : 'none';
    }
    if (chatNewDeckArea && chatNewDeckArea.style.display !== 'none') {
        // Only toggle if it was visible (deck complete state)
        chatNewDeckArea.style.display = tab === 'chat' ? 'flex' : 'none';
    }
    if (nerdContent) {
        nerdContent.style.display = tab === 'nerd' ? 'flex' : 'none';
    }
    
    // If switching to nerd tab and we have events, re-render them
    if (tab === 'nerd' && workflowEvents.length > 0) {
        rerenderAllEvents();
    }
}

/**
 * Legacy toggle function - now switches to nerd tab.
 */
export function toggleNerdInfo() {
    switchToTab(nerdTabActive ? 'chat' : 'nerd');
}

/**
 * Checks if nerd info tab is active.
 * @returns {boolean}
 */
export function isNerdInfoEnabled() {
    return nerdTabActive;
}

/**
 * Sets the filter for events.
 * @param {string|null} filter - The stage to filter by, or null for all
 */
function setFilter(filter) {
    currentFilter = filter;
    rerenderAllEvents();
}

/**
 * Gets the stage for an event type.
 * @param {string} type - The event type
 * @returns {string|null} - The stage name or null
 */
function getEventStage(type) {
    const stageMap = {
        'debug_workflow_search': 'search',
        'debug_slide_offered': 'offer',
        'debug_slide_critiqued': 'critique',
        'debug_judge_invoked': 'judge',
    };
    return stageMap[type] || null;
}

/**
 * Checks if an event matches the current filter.
 * @param {Object} event - The event to check
 * @returns {boolean}
 */
function matchesFilter(event) {
    if (!currentFilter) return true;
    
    const type = event.type || '';
    
    // Handle slide-specific filter (e.g., "slide-1", "slide-2")
    if (currentFilter.startsWith('slide-')) {
        const slideNum = parseInt(currentFilter.replace('slide-', ''));
        const eventPosition = event.position;
        
        // Match events for this specific slide position
        if (eventPosition && parseInt(eventPosition) === slideNum) {
            return true;
        }
        
        // Also match slide workflow events for this position
        if (type === 'debug_slide_workflow_start' || type === 'debug_slide_workflow_complete') {
            return event.position === slideNum;
        }
        
        return false;
    }
    
    // Check executor_start events
    if (type === 'debug_executor_start') {
        return event.executor === currentFilter;
    }
    
    // Check edge events
    if (type === 'debug_edge') {
        return event.to_node === currentFilter || event.from_node === currentFilter;
    }
    
    // Check by stage map
    const stage = getEventStage(type);
    if (stage) {
        return stage === currentFilter;
    }
    
    // Show phase events and slide workflow events always when filtering by stage
    if (type === 'debug_phase' || type === 'debug_slide_workflow_start' || 
        type === 'debug_slide_workflow_complete' || type === 'debug_search' ||
        type === 'debug_llm_start' || type === 'debug_llm_complete') {
        return true;
    }
    
    return true;
}

/**
 * Renders the fixed workflow graph header.
 * Shows: Outline → Slides (with per-slide workflow iterations)
 * @returns {string} HTML string
 */
function renderWorkflowGraphHeader() {
    // Main phase indicator
    const phaseInfo = {
        idle: { icon: '⏳', label: 'Ready' },
        search: { icon: '🔍', label: 'Searching' },
        outline: { icon: '📋', label: 'Outline' },
        slides: { icon: '🎯', label: 'Selecting Slides' }
    };
    
    const currentPhaseInfo = phaseInfo[currentPhase] || phaseInfo.idle;
    
    // Build slide workflow stages
    const stages = ['search', 'offer', 'critique', 'judge'];
    const stageInfo = {
        search: { icon: '🔎', label: 'Search' },
        offer: { icon: '🎁', label: 'Offer' },
        critique: { icon: '🧐', label: 'Critique' },
        judge: { icon: '⚖️', label: 'Judge' }
    };
    
    // Get attempt count - from filtered slide or current slide
    let displayAttempts = 0;
    if (currentFilter && currentFilter.startsWith('slide-')) {
        const filteredPos = parseInt(currentFilter.replace('slide-', ''));
        displayAttempts = slideWorkflows[filteredPos]?.attempts || 0;
    } else {
        displayAttempts = slideWorkflows[currentSlidePosition]?.attempts || 0;
    }
    const hasRetries = displayAttempts > 1;
    
    const stageNodes = stages.map((stage, idx) => {
        const info = stageInfo[stage];
        const isActive = currentStage === stage;
        const isFiltered = currentFilter === stage;
        const classes = [
            'nerd-graph-btn',
            isActive ? 'active' : '',
            isFiltered ? 'filtered' : ''
        ].filter(Boolean).join(' ');
        
        // Add connector after each stage except the last
        let connector = '';
        if (idx < stages.length - 1) {
            connector = '<span class="nerd-graph-connector">→</span>';
        }
        
        return `
            <button class="${classes}" data-stage="${stage}" title="Filter by ${info.label}">
                <span class="nerd-graph-icon">${info.icon}</span>
                <span class="nerd-graph-label">${info.label}</span>
            </button>
            ${connector}
        `;
    }).join('');
    
    // Add loop-back indicator (critique → search when rejected)
    const loopBackHtml = `
        <div class="nerd-loop-back ${hasRetries ? 'active' : ''}">
            <span class="nerd-loop-arrow">↩</span>
            ${displayAttempts > 0 ? `<span class="nerd-loop-count">${displayAttempts}×</span>` : ''}
        </div>
    `;
    
    // Build slide pills for navigation
    const slidePills = Object.keys(slideWorkflows).map(pos => {
        const sw = slideWorkflows[pos];
        const isActive = currentSlidePosition === parseInt(pos);
        const isFiltered = currentFilter === `slide-${pos}`;
        const statusClass = sw.complete ? (sw.success ? 'success' : 'failed') : 'pending';
        const classes = [
            'nerd-slide-pill',
            statusClass,
            isActive ? 'active' : '',
            isFiltered ? 'filtered' : ''
        ].filter(Boolean).join(' ');
        
        return `
            <button class="${classes}" data-slide="${pos}" title="Slide ${pos}: ${sw.topic || 'Untitled'}${sw.attempts ? ` (${sw.attempts} attempts)` : ''}">
                ${pos}
            </button>
        `;
    }).join('');
    
    return `
        <div class="nerd-workflow-header">
            <div class="nerd-workflow-overview">
                <div class="nerd-phase-indicator">
                    <span class="nerd-phase-icon">${currentPhaseInfo.icon}</span>
                    <span class="nerd-phase-label">${currentPhaseInfo.label}</span>
                    ${currentPhase === 'slides' && currentSlidePosition > 0 ? 
                        `<span class="nerd-slide-progress">Slide ${currentSlidePosition}/${totalSlides}</span>` : ''}
                </div>
                ${currentFilter ? `
                    <button class="nerd-clear-filter" title="Clear filter">
                        Filter: ${currentFilter} ✕
                    </button>
                ` : ''}
            </div>
            
            ${slidePills ? `
                <div class="nerd-slides-row">
                    <span class="nerd-slides-label">Slides:</span>
                    <div class="nerd-slide-pills">${slidePills}</div>
                </div>
            ` : ''}
            
            <div class="nerd-workflow-stages">
                <span class="nerd-stages-label">Workflow:</span>
                <div class="nerd-workflow-graph-nav">
                    ${stageNodes}
                </div>
                ${loopBackHtml}
            </div>
        </div>
    `;
}

/**
 * Gets the GitHub code link for a given file path.
 * @param {string} path - Relative path in the repo
 * @returns {string} HTML link
 */
function renderCodeLink(path) {
    if (!path) return '';
    const url = `${GITHUB_REPO}/${path}`;
    return `
        <a href="${escapeHtml(url)}" target="_blank" rel="noopener" class="nerd-inline-code-link" title="View source: ${escapeHtml(path)}">
            &lt;/&gt;
        </a>
    `;
}

/**
 * Attaches event handlers to the workflow header.
 */
function attachWorkflowHeaderHandlers() {
    const content = getById('nerd-info-content');
    if (!content) return;
    
    // Stage filter buttons
    content.querySelectorAll('.nerd-graph-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const stage = btn.dataset.stage;
            setFilter(currentFilter === stage ? null : stage);
        });
    });
    
    // Slide pill filter buttons
    content.querySelectorAll('.nerd-slide-pill').forEach(btn => {
        btn.addEventListener('click', () => {
            const slide = btn.dataset.slide;
            const filterKey = `slide-${slide}`;
            setFilter(currentFilter === filterKey ? null : filterKey);
        });
    });
    
    const clearBtn = content.querySelector('.nerd-clear-filter');
    if (clearBtn) {
        clearBtn.addEventListener('click', () => setFilter(null));
    }
}

/**
 * Sets up event delegation for thumbnail lightbox clicks and expand buttons.
 * This only needs to be called once since it uses event delegation.
 */
let thumbnailDelegationSetup = false;
function setupThumbnailDelegation() {
    if (thumbnailDelegationSetup) return;
    
    const content = getById('nerd-info-content');
    if (!content) return;
    
    // Use event delegation - listen on parent, handle clicks on thumbnails and expand buttons
    content.addEventListener('click', (e) => {
        // Handle thumbnail clicks
        const thumb = e.target.closest('.nerd-slide-thumb');
        if (thumb) {
            const src = thumb.dataset.src;
            const label = thumb.dataset.label || '';
            if (src) {
                showImageLightbox(src, label);
            }
            return;
        }
        
        // Handle expand prompt button clicks
        const expandBtn = e.target.closest('.nerd-expand-btn');
        if (expandBtn) {
            e.preventDefault();
            e.stopPropagation();
            const promptId = expandBtn.dataset.promptId;
            const eventEl = document.getElementById(`nerd-event-${promptId}`);
            if (eventEl && eventEl.dataset.fullPrompt) {
                showTextLightbox(eventEl.dataset.fullPrompt, 'Full Prompt');
            }
            return;
        }
    });
    
    thumbnailDelegationSetup = true;
}

/**
 * Updates workflow state from event.
 */
function updateWorkflowState(event) {
    const type = event.type || '';
    
    // Track main phases
    if (type === 'debug_phase') {
        const phase = event.phase || '';
        if (phase === 'search' || phase === 'initial_search') {
            currentPhase = 'search';
        } else if (phase === 'outline' || phase === 'outline_generation') {
            currentPhase = 'outline';
        } else if (phase === 'slide_selection') {
            currentPhase = 'slides';
        } else if (phase === 'complete') {
            currentPhase = 'idle';
            currentStage = 'idle';
        }
    }
    
    // Track slide workflow starts
    if (type === 'debug_slide_workflow_start') {
        currentSlidePosition = event.position || 0;
        totalSlides = event.total || totalSlides;
        currentStage = 'search';
        currentPhase = 'slides';
        
        // Initialize slide workflow tracking
        slideWorkflows[currentSlidePosition] = {
            topic: event.topic || '',
            attempts: 0,
            complete: false,
            success: false
        };
    }
    
    // Track executor changes
    if (type === 'debug_executor_start') {
        currentStage = event.executor || currentStage;
        
        // Track attempts
        if (slideWorkflows[currentSlidePosition]) {
            if (event.executor === 'offer') {
                slideWorkflows[currentSlidePosition].attempts = (event.attempt || 1);
            }
        }
    }
    
    // Track slide workflow completion
    if (type === 'debug_slide_workflow_complete') {
        if (slideWorkflows[event.position]) {
            slideWorkflows[event.position].complete = true;
            slideWorkflows[event.position].success = event.success;
            if (event.attempts) {
                slideWorkflows[event.position].attempts = event.attempts;
            }
        }
        currentStage = 'idle';
    }
    
    // Track edge transitions
    if (type === 'debug_edge') {
        currentStage = event.to_node || event.to || currentStage;
        if (currentStage === 'done') currentStage = 'idle';
    }
}

/**
 * Re-renders all stored events (used when enabling panel after events were collected).
 */
function rerenderAllEvents() {
    const content = getById('nerd-info-content');
    if (!content) return;
    
    // Render workflow header + events container
    content.innerHTML = `
        ${renderWorkflowGraphHeader()}
        <div class="nerd-events-container" id="nerd-events-container"></div>
    `;
    
    // Attach filter click handlers
    attachWorkflowHeaderHandlers();
    
    // Set up thumbnail lightbox delegation (only once)
    setupThumbnailDelegation();
    
    const eventsContainer = getById('nerd-events-container');
    if (!eventsContainer) return;
    
    // Filter and render events
    const filteredEvents = workflowEvents.filter(matchesFilter);
    
    if (filteredEvents.length === 0) {
        eventsContainer.innerHTML = `
            <div class="nerd-empty">
                <span class="nerd-empty-icon">🤓</span>
                <p>${currentFilter ? `No ${currentFilter} events yet` : 'Start building a deck to see the workflow'}</p>
            </div>
        `;
        return;
    }
    
    // Re-render each stored event
    for (const event of filteredEvents) {
        renderEventToContainer(event, eventsContainer);
    }
    
    scrollToBottom(eventsContainer);
}

/**
 * Renders a single event to a container.
 */
function renderEventToContainer(event, container) {
    const type = event.type || '';
    
    switch (type) {
        case 'debug_phase':
            renderPhaseEvent(event, container);
            break;
        case 'debug_search':
            renderSearchEvent(event, container);
            break;
        case 'debug_llm_start':
            renderLLMStartEvent(event, container);
            break;
        case 'debug_llm_complete':
            renderLLMCompleteEvent(event, container);
            break;
        case 'debug_slide_workflow_start':
            renderSlideWorkflowStart(event, container);
            break;
        case 'debug_slide_workflow_complete':
            renderSlideWorkflowComplete(event, container);
            break;
        case 'debug_executor_start':
            renderExecutorStart(event, container);
            break;
        case 'debug_edge':
            renderEdgeTransition(event, container);
            break;
        case 'debug_workflow_search':
            renderWorkflowSearch(event, container);
            break;
        case 'debug_slide_offered':
            renderSlideOffered(event, container);
            break;
        case 'debug_slide_critiqued':
            renderSlideCritiqued(event, container);
            break;
        case 'debug_judge_invoked':
            renderJudgeInvoked(event, container);
            break;
        case 'debug_fallback':
            renderFallback(event, container);
            break;
        default:
            if (type.startsWith('debug_')) {
                renderGenericEvent(event, container);
            }
    }
}

/**
 * Clears all workflow events.
 */
export function clearNerdInfo() {
    workflowEvents = [];
    eventCounter = 0;
    currentPhase = 'idle';
    currentStage = 'idle';
    currentSlidePosition = 0;
    totalSlides = 0;
    currentFilter = null;
    slideWorkflows = {};
    
    // Reset the counter badge
    updateEventCounterBadge();
    
    if (nerdTabActive) {
        rerenderAllEvents();
    }
}

/**
 * Handles all debug events from the SSE stream.
 * This is the single entry point for all debug event types.
 * @param {Object} data - The event data from backend
 */
export function handleDebugEvent(data) {
    // Skip code documentation event - we use inline links instead
    if (data.type === 'debug_code_links') {
        return;
    }
    
    // Always store events even if not displaying
    const event = {
        id: ++eventCounter,
        timestamp: new Date().toISOString(),
        ...data
    };
    workflowEvents.push(event);
    
    // Update the event counter badge
    updateEventCounterBadge();
    
    // Update current stage based on event
    updateWorkflowState(event);
    
    // Only render if nerd tab is active
    if (!nerdTabActive) return;
    
    // Update the workflow header
    const content = getById('nerd-info-content');
    const header = content?.querySelector('.nerd-workflow-header');
    if (header) {
        header.outerHTML = renderWorkflowGraphHeader();
        attachWorkflowHeaderHandlers();
    }
    
    // Only render event if it matches the current filter
    if (!matchesFilter(event)) return;
    
    const container = getById('nerd-events-container');
    if (!container) return;
    
    removeEmptyState(container);
    renderEventToContainer(event, container);
    scrollToBottom(container);
}

/**
 * Generates slide thumbnail HTML.
 * @param {string} sessionCode 
 * @param {number} slideNumber 
 * @param {string} [size='small'] - 'small' or 'medium'
 * @returns {string}
 */
function renderSlideThumbnail(sessionCode, slideNumber, size = 'small') {
    if (!sessionCode || !slideNumber) return '';
    
    // URL format: thumbnails/BRK121_25.png (relative path, underscore between code and number)
    const thumbUrl = `thumbnails/${sessionCode}_${slideNumber}.png`;
    const sizeClass = size === 'medium' ? 'nerd-thumb-medium' : 'nerd-thumb-small';
    const label = `${sessionCode} #${slideNumber}`;
    
    return `
        <div class="nerd-slide-thumb ${sizeClass}" data-src="${thumbUrl}" data-label="${escapeHtml(label)}" title="Click to enlarge">
            <img src="${thumbUrl}" alt="${label}" 
                 onerror="this.parentElement.classList.add('nerd-thumb-error')"
                 loading="lazy">
            <span class="nerd-thumb-label">${escapeHtml(sessionCode)} #${slideNumber}</span>
        </div>
    `;
}

/**
 * Renders multiple slide thumbnails.
 * @param {Array} slides - Array of {session_code, slide_number} or slide objects
 * @param {number} [maxShow=5] - Maximum to show
 * @returns {string}
 */
function renderSlideGallery(slides, maxShow = 5) {
    if (!slides || slides.length === 0) return '';
    
    const toShow = slides.slice(0, maxShow);
    const remaining = slides.length - maxShow;
    
    const thumbs = toShow.map(s => {
        const code = s.session_code || s.sessionCode;
        const num = s.slide_number || s.slideNumber;
        return renderSlideThumbnail(code, num, 'small');
    }).join('');
    
    return `
        <div class="nerd-slide-gallery">
            ${thumbs}
            ${remaining > 0 ? `<span class="nerd-gallery-more">+${remaining} more</span>` : ''}
        </div>
    `;
}

/**
 * Renders a phase event.
 */
function renderPhaseEvent(event, container) {
    if (!container) return;
    
    removeEmptyState(container);
    
    const phaseIcons = {
        'init': '🚀',
        'search': '🔍',
        'outline': '📋',
        'slide_selection': '🎯',
        'complete': '✅',
        'initial_search': '🔍',
        'outline_generation': '📋'
    };
    
    // Map phases to code paths
    const phasePaths = {
        'init': 'src/services/deck_builder/service.py',
        'search': 'src/services/search/service.py',
        'outline': 'src/services/deck_builder/agents.py',
        'slide_selection': 'src/services/deck_builder/workflow.py',
        'complete': 'src/services/deck_builder/service.py'
    };
    
    const codePath = phasePaths[event.phase];
    
    const el = createElement('nerd-event nerd-phase', event.id);
    el.innerHTML = `
        <div class="nerd-event-header">
            <span class="nerd-event-icon">${phaseIcons[event.phase] || '⚡'}</span>
            <span class="nerd-event-title">Phase: ${escapeHtml(event.phase)}</span>
            ${renderCodeLink(codePath)}
            <span class="nerd-event-time">${formatTime(event.timestamp)}</span>
        </div>
        <div class="nerd-event-desc">${escapeHtml(event.description || '')}</div>
    `;
    
    container.appendChild(el);
    scrollToBottom(container);
}

/**
 * Renders an initial search event.
 */
function renderSearchEvent(event, container) {
    if (!container) return;
    
    removeEmptyState(container);
    
    const el = createElement('nerd-event nerd-search', event.id);
    el.innerHTML = `
        <div class="nerd-event-header">
            <span class="nerd-event-icon">🔍</span>
            <span class="nerd-event-title">Initial Search</span>
            ${renderCodeLink('src/services/search/service.py')}
            <span class="nerd-event-time">${formatTime(event.timestamp)}</span>
        </div>
        <div class="nerd-search-query">"${escapeHtml(event.query || '')}"</div>
        <div class="nerd-search-meta">
            <span>${event.result_count || 0} results</span>
            ${event.duration_ms ? `<span>• ${event.duration_ms}ms</span>` : ''}
        </div>
        ${event.results ? renderSlideGallery(event.results, 6) : ''}
    `;
    
    container.appendChild(el);
    scrollToBottom(container);
}

/**
 * Renders an LLM call start event.
 */
function renderLLMStartEvent(event, container) {
    if (!container) return;
    
    removeEmptyState(container);
    
    // Map agent names to code paths
    const agentPaths = {
        'OutlineAgent': 'src/services/deck_builder/agents.py',
        'OfferAgent': 'src/services/deck_builder/executors/offer.py',
        'CritiqueAgent': 'src/services/deck_builder/executors/critique.py',
        'JudgeAgent': 'src/services/deck_builder/executors/judge.py'
    };
    const codePath = agentPaths[event.agent] || 'src/services/deck_builder/agents.py';
    
    const hasFullPrompt = event.full_prompt && event.full_prompt.length > 500;
    
    const el = createElement('nerd-event nerd-llm-call pending', event.id);
    el.innerHTML = `
        <div class="nerd-event-header nerd-llm-header">
            <span class="nerd-event-icon">🤖</span>
            <span class="nerd-event-title">${escapeHtml(event.agent || 'LLM')}</span>
            <span class="nerd-llm-status pending">⏳</span>
            ${renderCodeLink(codePath)}
            <span class="nerd-event-time">${formatTime(event.timestamp)}</span>
        </div>
        ${event.task ? `<div class="nerd-event-desc">${escapeHtml(event.task)}</div>` : ''}
        ${event.position ? `<div class="nerd-llm-meta">Slide Position: ${event.position}</div>` : ''}
        ${event.response_format ? `<div class="nerd-llm-meta">Format: <code>${escapeHtml(event.response_format)}</code></div>` : ''}
        ${event.prompt_preview ? `
            <details class="nerd-llm-section">
                <summary>
                    Prompt Preview
                    ${hasFullPrompt ? `<button class="nerd-expand-btn" data-prompt-id="${event.id}" title="View full prompt">Expand ↗</button>` : ''}
                </summary>
                <div class="nerd-llm-code">${escapeHtml(event.prompt_preview)}</div>
            </details>
        ` : ''}
    `;
    
    // Store full prompt for expand button
    if (hasFullPrompt) {
        el.dataset.fullPrompt = event.full_prompt;
    }
    
    container.appendChild(el);
    scrollToBottom(container);
}

/**
 * Renders an LLM call completion event.
 */
function renderLLMCompleteEvent(event, container) {
    if (!container) return;
    
    removeEmptyState(container);
    
    const isSuccess = event.status === 'success';
    const statusIcon = isSuccess ? '✓' : '✗';
    const statusClass = isSuccess ? 'complete' : 'error';
    
    // Map agent names to code paths
    const agentPaths = {
        'OutlineAgent': 'src/services/deck_builder/agents.py',
        'OfferAgent': 'src/services/deck_builder/executors/offer.py',
        'CritiqueAgent': 'src/services/deck_builder/executors/critique.py',
        'JudgeAgent': 'src/services/deck_builder/executors/judge.py'
    };
    const codePath = agentPaths[event.agent] || 'src/services/deck_builder/agents.py';
    
    const el = createElement(`nerd-event nerd-llm-call ${statusClass}`, event.id);
    el.innerHTML = `
        <div class="nerd-event-header nerd-llm-header">
            <span class="nerd-event-icon">🤖</span>
            <span class="nerd-event-title">${escapeHtml(event.agent || 'LLM')}</span>
            <span class="nerd-llm-status ${statusClass}">${statusIcon}</span>
            ${renderCodeLink(codePath)}
            <span class="nerd-event-time">${formatTime(event.timestamp)}</span>
        </div>
        <div class="nerd-llm-meta">
            ${event.duration_ms ? `Duration: ${event.duration_ms}ms` : ''}
            ${event.position ? ` • Position: ${event.position}` : ''}
        </div>
        ${event.response_preview ? `
            <div class="nerd-llm-section">
                <div class="nerd-llm-label">Response:</div>
                <div class="nerd-llm-code">${escapeHtml(event.response_preview)}</div>
            </div>
        ` : ''}
        ${event.error ? `
            <div class="nerd-llm-section nerd-error">
                <div class="nerd-llm-label">Error:</div>
                <div class="nerd-llm-code">${escapeHtml(event.error)}</div>
            </div>
        ` : ''}
    `;
    
    container.appendChild(el);
    scrollToBottom(container);
}

/**
 * Renders a slide workflow start event.
 */
function renderSlideWorkflowStart(event, container) {
    if (!container) return;
    
    removeEmptyState(container);
    
    // Always show code links for workflow executors
    const workflowLinks = [
        { name: 'workflow', path: 'src/services/deck_builder/workflow.py' },
        { name: 'search', path: 'src/services/deck_builder/executors/search.py' },
        { name: 'offer', path: 'src/services/deck_builder/executors/offer.py' },
        { name: 'critique', path: 'src/services/deck_builder/executors/critique.py' },
        { name: 'judge', path: 'src/services/deck_builder/executors/judge.py' }
    ];
    
    const linksHtml = workflowLinks.map(l => `
        <a href="${GITHUB_REPO}/${l.path}" target="_blank" rel="noopener" class="nerd-mini-code-link" title="${l.path}">
            ${l.name}
        </a>
    `).join('');
    
    const el = createElement('nerd-event nerd-slide-workflow', event.id);
    el.innerHTML = `
        <div class="nerd-slide-workflow-header">
            <span class="nerd-slide-pos">📊 Slide ${event.position}/${event.total || '?'}</span>
            <span class="nerd-slide-topic">${escapeHtml(event.topic || '')}</span>
        </div>
        <div class="nerd-slide-workflow-code-links">${linksHtml}</div>
    `;
    
    container.appendChild(el);
    scrollToBottom(container);
}

/**
 * Renders a slide workflow completion event.
 */
function renderSlideWorkflowComplete(event, container) {
    if (!container) return;
    
    const isSuccess = event.success;
    const el = createElement(`nerd-event nerd-slide-result ${isSuccess ? 'success' : 'failed'}`, event.id);
    
    let slideThumb = '';
    if (isSuccess && event.slide) {
        slideThumb = renderSlideThumbnail(
            event.slide.session_code, 
            event.slide.slide_number, 
            'medium'
        );
    }

    if (isSuccess && event.slide) {
        el.innerHTML = `
            <div class="nerd-result-header">
                <span class="nerd-result-icon">✅</span>
                <span>Slide ${event.position} → ${escapeHtml(event.slide.session_code || '')} #${event.slide.slide_number || ''}</span>
            </div>
            ${event.attempts ? `<div class="nerd-result-meta">Attempts: ${event.attempts}</div>` : ''}
            ${slideThumb}
        `;
    } else {
        el.innerHTML = `
            <div class="nerd-result-header">
                <span class="nerd-result-icon">❌</span>
                <span>Slide ${event.position}: No suitable slide found</span>
            </div>
        `;
    }
    
    container.appendChild(el);
    scrollToBottom(container);
}

/**
 * Renders an executor start event.
 */
function renderExecutorStart(event, container) {
    if (!container) return;
    
    removeEmptyState(container);
    
    const executorIcons = {
        'search': '🔎',
        'offer': '🎁',
        'critique': '🧐',
        'judge': '⚖️'
    };
    
    const executorPaths = {
        'search': 'src/services/deck_builder/executors/search.py',
        'offer': 'src/services/deck_builder/executors/offer.py',
        'critique': 'src/services/deck_builder/executors/critique.py',
        'judge': 'src/services/deck_builder/executors/judge.py'
    };
    const codePath = executorPaths[event.executor];
    
    const el = createElement(`nerd-event nerd-executor nerd-executor-${event.executor}`, event.id);
    el.innerHTML = `
        <div class="nerd-event-header">
            <span class="nerd-event-icon">${executorIcons[event.executor] || '⚙️'}</span>
            <span class="nerd-event-title">Executor: ${escapeHtml(event.executor)}</span>
            ${renderCodeLink(codePath)}
            <span class="nerd-event-time">${formatTime(event.timestamp)}</span>
        </div>
        <div class="nerd-executor-meta">
            Position: ${event.position || '?'}
            ${event.attempt ? ` • Attempt: ${event.attempt}` : ''}
            ${event.candidate_count ? ` • Candidates: ${event.candidate_count}` : ''}
        </div>
    `;
    
    container.appendChild(el);
    scrollToBottom(container);
}

/**
 * Renders an edge transition event.
 */
function renderEdgeTransition(event, container) {
    if (!container) return;
    
    removeEmptyState(container);
    
    const el = createElement('nerd-event nerd-edge', event.id);
    el.innerHTML = `
        <div class="nerd-edge-flow">
            <span class="nerd-edge-from">${escapeHtml(event.from_node || event.from || '?')}</span>
            <span class="nerd-edge-arrow">→</span>
            <span class="nerd-edge-to">${escapeHtml(event.to_node || event.to || '?')}</span>
            ${renderCodeLink('src/services/deck_builder/workflow.py')}
        </div>
        ${event.condition ? `<div class="nerd-edge-condition">${escapeHtml(event.condition)}</div>` : ''}
    `;
    
    container.appendChild(el);
    scrollToBottom(container);
}

/**
 * Renders a workflow search event (within slide workflow).
 */
function renderWorkflowSearch(event, container) {
    if (!container) return;
    
    removeEmptyState(container);
    
    const el = createElement('nerd-event nerd-workflow-search', event.id);
    el.innerHTML = `
        <div class="nerd-event-header">
            <span class="nerd-event-icon">${event.is_retry ? '🔄' : '🔍'}</span>
            <span class="nerd-event-title">Workflow Search</span>
            ${renderCodeLink('src/services/deck_builder/executors/search.py')}
            <span class="nerd-event-time">${formatTime(event.timestamp)}</span>
        </div>
        <div class="nerd-search-query">"${escapeHtml(event.query || '')}"</div>
        <div class="nerd-search-meta">
            <span>${event.result_count || 0} results</span>
            ${event.is_retry ? '<span class="nerd-retry-badge">retry</span>' : ''}
        </div>
        ${event.results ? renderSlideGallery(event.results, 4) : ''}
        ${event.previous_searches?.length > 0 ? `
            <div class="nerd-previous-searches">
                Previous: ${event.previous_searches.map(s => `"${escapeHtml(s)}"`).join(', ')}
            </div>
        ` : ''}
    `;
    
    container.appendChild(el);
    scrollToBottom(container);
}

/**
 * Renders a slide offered event.
 */
function renderSlideOffered(event, container) {
    if (!container) return;
    
    removeEmptyState(container);
    
    const thumb = renderSlideThumbnail(event.session_code, event.slide_number, 'medium');
    
    const el = createElement('nerd-event nerd-slide-offered', event.id);
    el.innerHTML = `
        <div class="nerd-event-header">
            <span class="nerd-event-icon">🎁</span>
            <span class="nerd-event-title">Slide Offered</span>
            ${renderCodeLink('src/services/deck_builder/executors/offer.py')}
            <span class="nerd-event-time">${formatTime(event.timestamp)}</span>
        </div>
        ${thumb}
        ${event.reason ? `<div class="nerd-offered-reason">${escapeHtml(event.reason)}</div>` : ''}
    `;
    
    container.appendChild(el);
    scrollToBottom(container);
}

/**
 * Renders a slide critiqued event.
 */
function renderSlideCritiqued(event, container) {
    if (!container) return;
    
    removeEmptyState(container);
    
    const isApproved = event.approved;
    const thumb = renderSlideThumbnail(event.session_code, event.slide_number, 'small');
    
    const el = createElement(`nerd-event nerd-critique ${isApproved ? 'approved' : 'rejected'}`, event.id);
    el.innerHTML = `
        <div class="nerd-event-header">
            <span class="nerd-event-icon">${isApproved ? '✅' : '❌'}</span>
            <span class="nerd-event-title">Critique: ${isApproved ? 'Approved' : 'Rejected'}</span>
            ${renderCodeLink('src/services/deck_builder/executors/critique.py')}
            <span class="nerd-event-time">${formatTime(event.timestamp)}</span>
        </div>
        <div class="nerd-critique-content">
            ${thumb}
            <div class="nerd-critique-details">
                <div class="nerd-critique-feedback">${escapeHtml(event.feedback || '')}</div>
                ${event.search_suggestion && !isApproved ? `
                    <div class="nerd-critique-suggestion">💡 Suggestion: "${escapeHtml(event.search_suggestion)}"</div>
                ` : ''}
            </div>
        </div>
    `;
    
    container.appendChild(el);
    scrollToBottom(container);
}

/**
 * Renders a judge invoked event.
 */
function renderJudgeInvoked(event, container) {
    if (!container) return;
    
    removeEmptyState(container);
    
    const selectedThumb = event.selected_code ? 
        renderSlideThumbnail(event.selected_code, event.selected_number, 'medium') : '';
    
    const el = createElement('nerd-event nerd-judge', event.id);
    el.innerHTML = `
        <div class="nerd-event-header">
            <span class="nerd-event-icon">⚖️</span>
            <span class="nerd-event-title">Judge Selection</span>
            ${renderCodeLink('src/services/deck_builder/executors/judge.py')}
            <span class="nerd-event-time">${formatTime(event.timestamp)}</span>
        </div>
        <div class="nerd-judge-info">
            Position ${event.position} • ${event.candidates_count || event.candidate_count || 0} candidates evaluated
        </div>
        ${event.candidates ? renderSlideGallery(event.candidates, 4) : ''}
        ${event.selected_code ? `
            <div class="nerd-judge-result">
                <span class="nerd-judge-label">Selected:</span>
                ${selectedThumb}
            </div>
        ` : ''}
        ${event.reason ? `<div class="nerd-judge-reason">${escapeHtml(event.reason)}</div>` : ''}
    `;
    
    container.appendChild(el);
    scrollToBottom(container);
}

/**
 * Renders a fallback event.
 */
function renderFallback(event, container) {
    if (!container) return;
    
    removeEmptyState(container);
    
    const el = createElement('nerd-event nerd-fallback', event.id);
    el.innerHTML = `
        <div class="nerd-event-header">
            <span class="nerd-event-icon">⚠️</span>
            <span class="nerd-event-title">Fallback Used</span>
            <span class="nerd-event-time">${formatTime(event.timestamp)}</span>
        </div>
        <div class="nerd-fallback-info">
            ${escapeHtml(event.description || 'Using fallback selection')}
        </div>
        ${event.fallback_slide ? `
            <div class="nerd-fallback-slide">Slide: ${escapeHtml(event.fallback_slide)}</div>
        ` : ''}
    `;
    
    container.appendChild(el);
    scrollToBottom(container);
}

/**
 * Renders a generic debug event.
 */
function renderGenericEvent(event, container) {
    if (!container) return;
    
    removeEmptyState(container);
    
    const el = createElement('nerd-event nerd-generic', event.id);
    const eventType = (event.type || 'debug').replace('debug_', '');
    
    el.innerHTML = `
        <div class="nerd-event-header">
            <span class="nerd-event-icon">📌</span>
            <span class="nerd-event-title">${escapeHtml(eventType)}</span>
            <span class="nerd-event-time">${formatTime(event.timestamp)}</span>
        </div>
        <details class="nerd-generic-details">
            <summary>Event Data</summary>
            <pre class="nerd-json">${escapeHtml(JSON.stringify(event, null, 2))}</pre>
        </details>
    `;
    
    container.appendChild(el);
    scrollToBottom(container);
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Creates a DOM element with classes and ID.
 */
function createElement(className, eventId) {
    const el = document.createElement('div');
    el.className = className;
    el.id = `nerd-event-${eventId}`;
    return el;
}

/**
 * Removes the empty state placeholder.
 */
function removeEmptyState(content) {
    const empty = content.querySelector('.nerd-empty');
    if (empty) {
        empty.remove();
    }
}

/**
 * Scrolls to bottom of content.
 */
function scrollToBottom(el) {
    el.scrollTop = el.scrollHeight;
}

/**
 * Shows an image in a lightbox overlay.
 * @param {string} src - Image source URL
 * @param {string} label - Image label/caption
 */
function showImageLightbox(src, label) {
    // Remove existing lightbox if any
    const existing = document.querySelector('.nerd-lightbox');
    if (existing) existing.remove();
    
    const lightbox = document.createElement('div');
    lightbox.className = 'nerd-lightbox';
    lightbox.innerHTML = `
        <div class="nerd-lightbox-backdrop"></div>
        <div class="nerd-lightbox-content">
            <button class="nerd-lightbox-close" title="Close">&times;</button>
            <img src="${src}" alt="${escapeHtml(label)}" />
            <div class="nerd-lightbox-label">${escapeHtml(label)}</div>
        </div>
    `;
    
    document.body.appendChild(lightbox);
    
    // Close on backdrop click or close button
    lightbox.querySelector('.nerd-lightbox-backdrop').addEventListener('click', () => lightbox.remove());
    lightbox.querySelector('.nerd-lightbox-close').addEventListener('click', () => lightbox.remove());
    
    // Close on escape key
    const handleEsc = (e) => {
        if (e.key === 'Escape') {
            lightbox.remove();
            document.removeEventListener('keydown', handleEsc);
        }
    };
    document.addEventListener('keydown', handleEsc);
}

/**
 * Shows text content in a lightbox overlay (for full prompts).
 * @param {string} text - The text content to display
 * @param {string} title - Title for the lightbox
 */
function showTextLightbox(text, title) {
    // Remove existing lightbox if any
    const existing = document.querySelector('.nerd-lightbox');
    if (existing) existing.remove();
    
    const lightbox = document.createElement('div');
    lightbox.className = 'nerd-lightbox nerd-lightbox-text';
    lightbox.innerHTML = `
        <div class="nerd-lightbox-backdrop"></div>
        <div class="nerd-lightbox-content nerd-lightbox-text-content">
            <div class="nerd-lightbox-header">
                <span class="nerd-lightbox-title">${escapeHtml(title)}</span>
                <button class="nerd-lightbox-close" title="Close">&times;</button>
            </div>
            <pre class="nerd-lightbox-text-body">${escapeHtml(text)}</pre>
        </div>
    `;
    
    document.body.appendChild(lightbox);
    
    // Close on backdrop click or close button
    lightbox.querySelector('.nerd-lightbox-backdrop').addEventListener('click', () => lightbox.remove());
    lightbox.querySelector('.nerd-lightbox-close').addEventListener('click', () => lightbox.remove());
    
    // Close on escape key
    const handleEsc = (e) => {
        if (e.key === 'Escape') {
            lightbox.remove();
            document.removeEventListener('keydown', handleEsc);
        }
    };
    document.addEventListener('keydown', handleEsc);
}

/**
 * Updates the event counter badge in the Nerd tab.
 */
function updateEventCounterBadge() {
    const badge = document.querySelector('#nerd-tab .nerd-event-count');
    if (badge) {
        badge.textContent = workflowEvents.length;
        badge.style.display = workflowEvents.length > 0 ? 'inline-flex' : 'none';
    }
}

/**
 * Formats timestamp for display.
 */
function formatTime(isoString) {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', { 
        hour12: false, 
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit' 
    });
}

/**
 * Gets all workflow events (for debugging/export).
 * @returns {Array<Object>}
 */
export function getWorkflowEvents() {
    return [...workflowEvents];
}
