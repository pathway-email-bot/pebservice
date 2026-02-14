/**
 * Firebase Authentication Service
 * 
 * Handles magic link (email link) authentication for the student portal.
 */

import {
    sendSignInLinkToEmail,
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

// Action code settings for the magic link
const getActionCodeSettings = () => {
    // Redirect back to the root URL after clicking the link.
    // main.ts routes by auth state, so no subpath is needed —
    // once sign-in completes, the auth listener shows scenarios automatically.
    const settings = {
        url: window.location.origin + import.meta.env.BASE_URL,
        handleCodeInApp: true,
    };

    debugLog('Action code settings:', settings);
    return settings;
};

/**
 * Send a magic link to the user's email
 */
export async function sendMagicLink(email: string): Promise<void> {
    debugLog('Attempting to send magic link', { email });

    try {
        const actionCodeSettings = getActionCodeSettings();

        debugLog('Calling sendSignInLinkToEmail...');
        await sendSignInLinkToEmail(auth, email, actionCodeSettings);

        debugLog('Magic link sent successfully!');

        // Save email to localStorage for when they click the link
        window.localStorage.setItem('emailForSignIn', email);
        debugLog('Email saved to localStorage');

    } catch (error: any) {
        debugError('Failed to send magic link', error);

        // Re-throw with more context
        if (error.code === 'auth/operation-not-allowed') {
            throw new Error('Email link sign-in is not enabled. Please contact support.');
        } else if (error.code === 'auth/invalid-email') {
            throw new Error('Invalid email address. Please check and try again.');
        } else if (error.code === 'auth/unauthorized-domain') {
            throw new Error('This domain is not authorized. Please contact support.');
        } else {
            throw new Error(error.message || 'Failed to send login link. Please try again.');
        }
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
