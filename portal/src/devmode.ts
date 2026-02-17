/**
 * Devmode — centralized developer/testing mode for the portal.
 *
 * Activated via the `?devmode` query parameter:
 *   ?devmode              → active with no specific flags (default mode)
 *   ?devmode=preview      → active with "preview" flag
 *
 * Usage:
 *   import { devmode } from '../devmode';
 *
 *   if (devmode.active) { ... }           // any devmode
 *   if (devmode.has('preview')) ...        // specific flag
 *   console.log(devmode.flags);           // Set of all flags
 *
 * Flags:
 *   preview   — auto-activate the first scenario for UX debugging
 */

const params = new URLSearchParams(window.location.search);
const raw = params.get('devmode');

/** Whether ?devmode is present at all */
const active = params.has('devmode');

/** Parsed set of comma-separated flags (empty set if just ?devmode with no value) */
const flags: ReadonlySet<string> = new Set(
    raw ? raw.split(',').map(f => f.trim().toLowerCase()).filter(Boolean) : []
);

/** Check whether a specific flag is active */
function has(flag: string): boolean {
    return flags.has(flag.toLowerCase());
}

if (active) {
    console.info(`[devmode] Active — flags: ${flags.size ? [...flags].join(', ') : '(none)'}`);
}

export const devmode = { active, flags, has } as const;
