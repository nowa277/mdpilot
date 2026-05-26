import './styles/globals.css';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from './app/App';
import { ensureUserId } from './shared/identity';

async function bootstrap() {
  ensureUserId();
  if (import.meta.env.VITE_API_MODE === 'mock') {
    const { startMocks } = await import('./mocks');
    await startMocks();
  }
  const rootEl = document.getElementById('root');
  if (!rootEl) throw new Error('#root not found');
  createRoot(rootEl).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

void bootstrap();
