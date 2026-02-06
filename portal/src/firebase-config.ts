import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';

// Firebase configuration - generated via CLI
// npx firebase-tools apps:sdkconfig WEB 1:687061619628:web:6d94d1f35ca45176c16009
const firebaseConfig = {
    apiKey: "AIzaSyDj6y-LGt91jSR8l9H0kihm5jsf3c9uqBU",
    authDomain: "pathway-email-bot-6543.firebaseapp.com",
    projectId: "pathway-email-bot-6543",
    storageBucket: "pathway-email-bot-6543.firebasestorage.app",
    messagingSenderId: "687061619628",
    appId: "1:687061619628:web:6d94d1f35ca45176c16009"
};

// Initialize Firebase
export const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app, 'pathway');
