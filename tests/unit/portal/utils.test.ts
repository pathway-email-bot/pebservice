/**
 * Unit tests for portal utility functions.
 *
 * escapeHtml is the security layer that prevents XSS when rendering
 * user-supplied names in innerHTML. These tests verify that all
 * HTML-sensitive characters are properly escaped.
 */

import { describe, it, expect } from 'vitest';
import { escapeHtml } from '../../../portal/src/utils';

describe('escapeHtml', () => {
    it('escapes angle brackets', () => {
        expect(escapeHtml('<script>alert("xss")</script>')).toBe(
            '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;'
        );
    });

    it('escapes ampersands', () => {
        expect(escapeHtml('Tom & Jerry')).toBe('Tom &amp; Jerry');
    });

    it('escapes double quotes', () => {
        expect(escapeHtml('He said "hello"')).toBe('He said &quot;hello&quot;');
    });

    it('leaves normal names unchanged', () => {
        expect(escapeHtml('Sarah')).toBe('Sarah');
        expect(escapeHtml("O'Brien")).toBe("O'Brien");
        expect(escapeHtml('María José')).toBe('María José');
        expect(escapeHtml('김민수')).toBe('김민수');
        expect(escapeHtml('Müller-Schmidt')).toBe('Müller-Schmidt');
    });

    it('handles empty string', () => {
        expect(escapeHtml('')).toBe('');
    });

    it('handles combined dangerous characters', () => {
        expect(escapeHtml('<img src="x" onerror="alert(1)">')).toBe(
            '&lt;img src=&quot;x&quot; onerror=&quot;alert(1)&quot;&gt;'
        );
    });
});
