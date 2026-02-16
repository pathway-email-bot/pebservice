/**
 * Shared utility functions for the portal.
 */

/** Escape HTML special characters to prevent XSS when interpolating into innerHTML */
export function escapeHtml(s: string): string {
    return s
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
