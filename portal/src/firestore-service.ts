/**
 * Firestore service for managing user attempts and scenarios
 */
import { db, auth } from './firebase-config';
import { collection, doc, onSnapshot, Unsubscribe, query, where, orderBy, limit, setDoc, getDocs, updateDoc } from 'firebase/firestore';

export interface Attempt {
    id: string;
    scenarioId: string;
    status: 'pending' | 'graded' | 'abandoned';
    startedAt: Date;
    score?: number;
    maxScore?: number;
    feedback?: string;
    gradedAt?: Date;
}

export interface UserData {
    activeScenarioId: string | null;
    activeAttemptId: string | null;
}

/**
 * Create a new attempt for a scenario in Firestore
 * Also updates user's activeScenarioId and activeAttemptId
 */
export async function createAttempt(scenarioId: string): Promise<string> {
    const user = auth.currentUser;
    if (!user?.email) {
        throw new Error('User not authenticated');
    }

    const attemptsRef = collection(db, 'users', user.email, 'attempts');
    const attemptRef = doc(attemptsRef);
    
    const now = new Date();
    await setDoc(attemptRef, {
        scenarioId,
        status: 'pending',
        startedAt: now,
    });
    
    // Update user's active scenario and attempt
    const userRef = doc(db, 'users', user.email);
    await setDoc(userRef, {
        activeScenarioId: scenarioId,
        activeAttemptId: attemptRef.id,
    }, { merge: true });
    
    return attemptRef.id;
}

/**
 * Listen to user's active scenario
 */
export function listenToUserData(callback: (data: UserData | null) => void): Unsubscribe {
    const user = auth.currentUser;
    if (!user?.email) {
        throw new Error('User not authenticated');
    }

    const userRef = doc(db, 'users', user.email);

    return onSnapshot(userRef, (snapshot) => {
        if (snapshot.exists()) {
            callback(snapshot.data() as UserData);
        } else {
            callback(null);
        }
    });
}

/**
 * Listen to all attempts for the current user
 */
export function listenToAttempts(callback: (attempts: Attempt[]) => void): Unsubscribe {
    const user = auth.currentUser;
    if (!user?.email) {
        throw new Error('User not authenticated');
    }

    const attemptsRef = collection(db, 'users', user.email, 'attempts');
    const q = query(attemptsRef, orderBy('startedAt', 'desc'));

    return onSnapshot(q, (snapshot) => {
        const attempts = snapshot.docs.map((doc) => {
            const data = doc.data();
            return {
                id: doc.id,
                scenarioId: data.scenarioId,
                status: data.status,
                startedAt: data.startedAt?.toDate() || new Date(),
                score: data.score,
                maxScore: data.maxScore,
                feedback: data.feedback,
                gradedAt: data.gradedAt?.toDate(),
            };
        });
        callback(attempts);
    });
}

/**
 * Listen to the current active attempt (most recent pending/awaiting_student_email)
 */
export function listenToActiveAttempt(callback: (attempt: Attempt | null) => void): Unsubscribe {
    const user = auth.currentUser;
    if (!user?.email) {
        throw new Error('User not authenticated');
    }

    const attemptsRef = collection(db, 'users', user.email, 'attempts');
    const q = query(
        attemptsRef,
        where('status', '==', 'pending'),
        orderBy('startedAt', 'desc'),
        limit(1)
    );

    return onSnapshot(q, (snapshot) => {
        if (snapshot.empty) {
            callback(null);
        } else {
            const doc = snapshot.docs[0];
            const data = doc.data();
            callback({
                id: doc.id,
                scenarioId: data.scenarioId,
                status: data.status,
                startedAt: data.startedAt?.toDate() || new Date(),
                score: data.score,
                maxScore: data.maxScore,
                feedback: data.feedback,
                gradedAt: data.gradedAt?.toDate(),
            });
        }
    });
}

/**
 * Listen to a specific attempt
 */
export function listenToAttempt(attemptId: string, callback: (attempt: Attempt | null) => void): Unsubscribe {
    const user = auth.currentUser;
    if (!user?.email) {
        throw new Error('User not authenticated');
    }

    const attemptRef = doc(db, 'users', user.email, 'attempts', attemptId);

    return onSnapshot(attemptRef, (snapshot) => {
        if (snapshot.exists()) {
            const data = snapshot.data();
            callback({
                id: snapshot.id,
                scenarioId: data.scenarioId,
                status: data.status,
                startedAt: data.startedAt?.toDate() || new Date(),
                score: data.score,
                maxScore: data.maxScore,
                feedback: data.feedback,
                gradedAt: data.gradedAt?.toDate(),
            });
        } else {
            callback(null);
        }
    });
}

/**
 * Abandon the current active attempt
 */
export async function abandonAttempt(attemptId: string): Promise<void> {
    const user = auth.currentUser;
    if (!user?.email) {
        throw new Error('User not authenticated');
    }

    const attemptRef = doc(db, 'users', user.email, 'attempts', attemptId);
    await setDoc(attemptRef, { status: 'abandoned' }, { merge: true });
}
