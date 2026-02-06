import './style.css';
import { renderLoginPage } from './pages/login';
import { renderScenariosPage } from './pages/scenarios';

// Simple router based on URL path
const app = document.querySelector<HTMLDivElement>('#app')!;
const path = window.location.pathname;

// Get the base path from Vite config (e.g., '/pebservice/' in production, '/' in dev)
const basePath = import.meta.env.BASE_URL;

// Normalize paths by removing trailing slashes for comparison
const normalizePath = (p: string) => p.replace(/\/$/, '');
const normalizedPath = normalizePath(path);
const scenariosPath = normalizePath(basePath + 'scenarios');

// Route to appropriate page
if (normalizedPath === scenariosPath) {
    renderScenariosPage(app);
} else {
    // Default to login page
    renderLoginPage(app);
}
