import './style.css';
import { renderLoginPage } from './pages/login';
import { renderScenariosPage } from './pages/scenarios';

// Simple router based on URL path
const app = document.querySelector<HTMLDivElement>('#app')!;
const path = window.location.pathname;

// Route to appropriate page
if (path === '/scenarios' || path === '/scenarios/') {
    renderScenariosPage(app);
} else {
    // Default to login page
    renderLoginPage(app);
}
