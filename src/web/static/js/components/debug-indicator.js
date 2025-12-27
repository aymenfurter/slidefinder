/**
 * Debug Indicator Component
 * Shows debug mode status and trace count in the UI.
 * @module components/debug-indicator
 */

'use strict';

import { fetchDebugStatus } from '../services/api.js';
import { getById } from '../utils/dom.js';

const UPDATE_INTERVAL = 30000;

/** Interval ID for cleanup */
let updateIntervalId = null;

/**
 * Updates the debug indicator UI with current status.
 * @param {Object} status - Debug status from API
 */
function updateDebugUI(status) {
    const indicator = getById('debug-indicator');
    const traceCount = getById('trace-count');
    
    if (!indicator) return;
    
    if (status.debug_mode) {
        indicator.style.display = 'flex';
        if (traceCount) {
            const count = status.trace_count || 0;
            traceCount.textContent = `${count} trace${count !== 1 ? 's' : ''}`;
        }
    } else {
        indicator.style.display = 'none';
    }
}

/**
 * Fetches and updates the debug status.
 */
async function refreshDebugStatus() {
    try {
        const status = await fetchDebugStatus();
        updateDebugUI(status);
    } catch (error) {
        console.debug('[DebugIndicator] Could not fetch debug status:', error.message);
    }
}

/**
 * Initializes the debug indicator.
 * Checks debug mode and sets up periodic updates.
 */
export function initDebugIndicator() {
    // Initial fetch
    refreshDebugStatus();
    
    // Set up periodic updates (only if debug mode is enabled)
    updateIntervalId = setInterval(refreshDebugStatus, UPDATE_INTERVAL);
    
    console.log('[DebugIndicator] Initialized');
}

/**
 * Stops the debug indicator updates.
 */
export function stopDebugIndicator() {
    if (updateIntervalId) {
        clearInterval(updateIntervalId);
        updateIntervalId = null;
    }
}

export default {
    initDebugIndicator,
    stopDebugIndicator,
    refreshDebugStatus
};
