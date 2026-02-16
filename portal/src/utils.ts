/**
 * Shared utility functions for the portal.
 */

/**
 * Escape HTML special characters when interpolating into innerHTML.
 *
 * Security: Firestore rules reject names containing '<' or '>' at write time
 * (see firestore.rules → isValidFirstName), so stored data can never contain
 * HTML tags — XSS is blocked at the data layer.
 *
 * This function escapes the remaining characters (& and ") for display
 * correctness — e.g. preventing '&' from starting an HTML entity or '"'
 * from breaking an attribute boundary in rendered templates.
 */
export function escapeHtml(s: string): string {
    return s
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
