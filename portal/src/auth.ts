import {
    isSignInWithEmailLink,
    signInWithEmailLink,
    onAuthStateChanged,
    signOut,
} from 'firebase/auth';
import type { User } from 'firebase/auth';
import { auth } from './firebase-config';

// Debug logging (only in development)
const isDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

function debugLog(message: string, data?: any) {
    if (isDev) {
        console.log(`[Auth Debug] ${message}`, data || '');
    }
}

function debugError(message: string, error: any) {
    if (isDev) {
        console.error(`[Auth Error] ${message}`, error);
    }
}

const CLOUD_FUNCTION_BASE_URL = 'https://us-central1-pathway-email-bot-6543.cloudfunctions.net';

/**
 * Send a magic link to the user's email via our Cloud Function.
 * 
 * The link is generated server-side by Firebase Admin SDK and sent
 * via the bot's Gmail API account (better deliverability than Firebase's
 * shared noreply@...firebaseapp.com domain).
 */
export async function sendMagicLink(email: string): Promise<void> {
    debugLog('Attempting to send magic link', { email });

    // DEV mock — Vite strips this from production builds
    if (import.meta.env.DEV) {
        console.info(`[DEV MOCK] sendMagicLink("${email}") — skipping API call`);
        await new Promise(r => setTimeout(r, 1000)); // simulate latency
        window.localStorage.setItem('emailForSignIn', email);
        return;
    }

    try {
        debugLog('Calling send_magic_link Cloud Function...');

        const response = await fetch(`${CLOUD_FUNCTION_BASE_URL}/send_magic_link`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email }),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const errorMessage = errorData.error || 'Failed to send login link';
            debugError('Cloud Function error', { status: response.status, errorMessage });

            if (response.status === 429) {
                // Rate limited — server message includes specific wait time
                throw new Error(errorMessage);
            }
            if (response.status === 400) {
                throw new Error('Invalid email address. Please check and try again.');
            }
            throw new Error(errorMessage);
        }

        debugLog('Magic link sent successfully!');

        // Save email to localStorage for when they click the link
        window.localStorage.setItem('emailForSignIn', email);
        debugLog('Email saved to localStorage');

    } catch (error: any) {
        debugError('Failed to send magic link', error);

        // Re-throw — the error message is already user-friendly
        if (error instanceof Error) {
            throw error;
        }
        throw new Error('Failed to send login link. Please try again.');
    }
}

/**
 * Complete sign-in after clicking the magic link
 * Call this on page load to check if we're returning from a magic link
 */
export async function completeMagicLinkSignIn(): Promise<User | null> {
    debugLog('Checking if URL is a sign-in link', { url: window.location.href });

    // Check if the URL is a sign-in link
    if (!isSignInWithEmailLink(auth, window.location.href)) {
        debugLog('URL is not a sign-in link');
        return null;
    }

    debugLog('URL is a sign-in link! Attempting to complete sign-in...');

    // Get the email from localStorage
    let email = window.localStorage.getItem('emailForSignIn');
    debugLog('Email from localStorage:', email);

    // If missing (different browser/device), redirect to login
    if (!email) {
        debugLog('Email not in localStorage - link opened in different browser/device');
        window.location.href = '/?error=different-browser';
        return null;
    }

    try {
        debugLog('Calling signInWithEmailLink...');
        const result = await signInWithEmailLink(auth, email, window.location.href);

        debugLog('Sign-in successful!', { user: result.user.email });

        // Clean up
        window.localStorage.removeItem('emailForSignIn');
        debugLog('Cleaned up localStorage');

        return result.user;
    } catch (error: any) {
        debugError('Failed to complete sign-in', error);

        // Show user-friendly error
        if (error.code === 'auth/invalid-action-code') {
            throw new Error('This link has expired or already been used. Please request a new one.');
        } else if (error.code === 'auth/invalid-email') {
            throw new Error('Invalid email address. Please try again.');
        } else {
            throw new Error(error.message || 'Failed to sign in. Please try again.');
        }
    }
}

/**
 * Sign out the current user
 */
export async function logout(): Promise<void> {
    debugLog('Signing out...');
    try {
        await signOut(auth);
        debugLog('Sign-out successful');
    } catch (error) {
        debugError('Sign-out failed', error);
        throw error;
    }
}

/**
 * Get the current user (null if not logged in)
 */
export function getCurrentUser(): User | null {
    const user = auth.currentUser;
    debugLog('Current user:', user?.email || 'none');
    return user;
}

/**
 * Subscribe to auth state changes
 */
export function onAuthChange(callback: (user: User | null) => void): () => void {
    debugLog('Setting up auth state listener');
    return onAuthStateChanged(auth, (user) => {
        debugLog('Auth state changed:', user?.email || 'signed out');
        callback(user);
    });
}
