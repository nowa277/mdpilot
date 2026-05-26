import { setupWorker } from 'msw/browser';

import { restHandlers } from './handlers';
import { startChatMockServers, startTaskMockServers } from './ws-server';

let started = false;

export async function startMocks(): Promise<void> {
  if (started) return;
  started = true;

  const worker = setupWorker(...restHandlers);
  await worker.start({
    onUnhandledRequest: 'bypass',
    serviceWorker: { url: '/mockServiceWorker.js' },
  });

  startChatMockServers();
  startTaskMockServers();

  // eslint-disable-next-line no-console
  console.info('[mocks] MSW + WS started');
}
