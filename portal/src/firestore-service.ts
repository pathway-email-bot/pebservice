/**
 * Firestore service for managing user attempts and scenarios
 */
import { db, auth } from './firebase-config';
import { collection, doc, onSnapshot, query, where, orderBy, limit, setDoc } from 'firebase/firestore';

export interface RubricScore {
    name: string;
    score: number;
    maxScore: number;
    justification?: string;
}

export interface Attempt {
    id: string;
    scenarioId: string;
    status: 'pending' | 'grading' | 'graded' | 'abandoned';
    startedAt: Date;
    score?: number;
    maxScore?: number;
    feedback?: string;
    gradedAt?: Date;
    rubricScores?: RubricScore[];
    revisionExample?: string;
}

export interface UserData {
    activeScenarioId: string | null;
    activeAttemptId: string | null;
    firstName?: string;
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
export function listenToUserData(callback: (data: UserData | null) => void): () => void {
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
 * Set the student's first name in their Firestore user doc
 */
export async function setFirstName(name: string): Promise<void> {
    const user = auth.currentUser;
    if (!user?.email) {
        throw new Error('User not authenticated');
    }

    const userRef = doc(db, 'users', user.email);
    await setDoc(userRef, { firstName: name.trim() }, { merge: true });
}

/**
 * Listen to all attempts for the current user
 */
export function listenToAttempts(callback: (attempts: Attempt[]) => void): () => void {
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
                rubricScores: data.rubricScores,
                revisionExample: data.revisionExample,
            };
        });
        console.info(`[Firestore] Loaded ${attempts.length} attempts`);
        callback(attempts);
    }, (error) => {
        console.error('[Firestore] listenToAttempts error:', error);
    });
}

/**
 * Listen to the current active attempt (most recent pending/awaiting_student_email)
 */
export function listenToActiveAttempt(callback: (attempt: Attempt | null) => void): () => void {
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
                rubricScores: data.rubricScores,
                revisionExample: data.revisionExample,
            });
        }
    });
}

/**
 * Listen to a specific attempt
 */
export function listenToAttempt(attemptId: string, callback: (attempt: Attempt | null) => void): () => void {
    const user = auth.currentUser;
    if (!user?.email) {
        throw new Error('User not authenticated');
    }

    const attemptRef = doc(db, 'users', user.email, 'attempts', attemptId);

    return onSnapshot(attemptRef, (snapshot) => {
        if (snapshot.exists()) {
            const data = snapshot.data();
            console.info(`[Firestore] Attempt ${attemptId} status: ${data.status}`);
            callback({
                id: snapshot.id,
                scenarioId: data.scenarioId,
                status: data.status,
                startedAt: data.startedAt?.toDate() || new Date(),
                score: data.score,
                maxScore: data.maxScore,
                feedback: data.feedback,
                gradedAt: data.gradedAt?.toDate(),
                rubricScores: data.rubricScores,
                revisionExample: data.revisionExample,
            });
        } else {
            console.warn(`[Firestore] Attempt ${attemptId} not found`);
            callback(null);
        }
    }, (error) => {
        console.error(`[Firestore] listenToAttempt(${attemptId}) error:`, error);
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
