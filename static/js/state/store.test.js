/**
 * Unit Tests for State Store
 * @module state/store.test
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
    getState,
    get,
    setState,
    subscribe,
    resetState,
    resetDeckBuilder,
    updateCache,
    getFromCache,
    hasInCache
} from '../state/store.js';

describe('getState', () => {
    beforeEach(() => {
        resetState();
    });

    it('should return current state', () => {
        const state = getState();
        expect(state).toBeDefined();
        expect(typeof state).toBe('object');
    });

    it('should return a copy of state', () => {
        const state1 = getState();
        const state2 = getState();
        expect(state1).not.toBe(state2);
        expect(state1).toEqual(state2);
    });

    it('should have expected initial properties', () => {
        const state = getState();
        expect(state.currentQuery).toBe('');
        expect(state.isSearching).toBe(false);
        expect(state.favorites).toEqual([]);
        expect(state.deckSlides).toEqual([]);
    });
});

describe('get', () => {
    beforeEach(() => {
        resetState();
    });

    it('should return specific state value', () => {
        expect(get('currentQuery')).toBe('');
        expect(get('isSearching')).toBe(false);
    });

    it('should return undefined for non-existent key', () => {
        expect(get('nonExistentKey')).toBeUndefined();
    });
});

describe('setState', () => {
    beforeEach(() => {
        resetState();
    });

    it('should update state values', () => {
        setState({ currentQuery: 'test' });
        expect(get('currentQuery')).toBe('test');
    });

    it('should update multiple values at once', () => {
        setState({
            currentQuery: 'search',
            isSearching: true
        });
        expect(get('currentQuery')).toBe('search');
        expect(get('isSearching')).toBe(true);
    });

    it('should only update specified keys', () => {
        setState({ currentQuery: 'test' });
        expect(get('isSearching')).toBe(false);
    });
});

describe('subscribe', () => {
    beforeEach(() => {
        resetState();
    });

    it('should call callback when subscribed key changes', () => {
        const callback = vi.fn();
        subscribe('currentQuery', callback);
        
        setState({ currentQuery: 'new value' });
        
        expect(callback).toHaveBeenCalledWith('new value', 'currentQuery');
    });

    it('should not call callback when other keys change', () => {
        const callback = vi.fn();
        subscribe('currentQuery', callback);
        
        setState({ isSearching: true });
        
        expect(callback).not.toHaveBeenCalled();
    });

    it('should return unsubscribe function', () => {
        const callback = vi.fn();
        const unsubscribe = subscribe('currentQuery', callback);
        
        unsubscribe();
        setState({ currentQuery: 'new value' });
        
        expect(callback).not.toHaveBeenCalled();
    });

    it('should support subscribing to multiple keys', () => {
        const callback = vi.fn();
        subscribe(['currentQuery', 'isSearching'], callback);
        
        setState({ currentQuery: 'test' });
        expect(callback).toHaveBeenCalledTimes(1);
        
        setState({ isSearching: true });
        expect(callback).toHaveBeenCalledTimes(2);
    });

    it('should support global subscription with "*"', () => {
        const callback = vi.fn();
        subscribe('*', callback);
        
        setState({ currentQuery: 'test' });
        
        expect(callback).toHaveBeenCalled();
    });
});

describe('resetState', () => {
    it('should reset all state to initial values', () => {
        setState({
            currentQuery: 'test',
            isSearching: true,
            favorites: [{ id: 1 }]
        });
        
        resetState();
        
        expect(get('currentQuery')).toBe('');
        expect(get('isSearching')).toBe(false);
        expect(get('favorites')).toEqual([]);
    });
});

describe('resetDeckBuilder', () => {
    beforeEach(() => {
        resetState();
    });

    it('should reset only deck builder state', () => {
        setState({
            deckSessionId: 'session-123',
            deckSlides: [{ id: 1 }],
            currentQuery: 'test'
        });
        
        resetDeckBuilder();
        
        expect(get('deckSessionId')).toBeNull();
        expect(get('deckSlides')).toEqual([]);
        expect(get('currentQuery')).toBe('test'); // Should not be reset
    });
});

describe('cache functions', () => {
    beforeEach(() => {
        resetState();
    });

    it('updateCache should add item to cache', () => {
        updateCache('query1', { results: [] });
        expect(hasInCache('query1')).toBe(true);
    });

    it('getFromCache should return cached item', () => {
        updateCache('query1', { results: [1, 2, 3] });
        expect(getFromCache('query1')).toEqual({ results: [1, 2, 3] });
    });

    it('getFromCache should return undefined for non-existent key', () => {
        expect(getFromCache('nonexistent')).toBeUndefined();
    });

    it('hasInCache should return false for non-existent key', () => {
        expect(hasInCache('nonexistent')).toBe(false);
    });

    it('should maintain cache size limit', () => {
        // Add more than 50 items
        for (let i = 0; i < 55; i++) {
            updateCache(`key${i}`, { value: i });
        }
        
        // First few items should be evicted
        expect(hasInCache('key0')).toBe(false);
        expect(hasInCache('key54')).toBe(true);
    });
});
