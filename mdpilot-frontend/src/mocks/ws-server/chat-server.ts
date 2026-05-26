import { Server } from 'mock-socket';

import { scenarios } from '../fixtures';
import { playScript } from '../scripts/play';

export interface ChatMockServers {
  servers: Server[];
  stop(): void;
}

export function startChatMockServers(): ChatMockServers {
  const servers: Server[] = [];

  const wsBase = (() => {
    const explicit = import.meta.env.VITE_WS_BASE;
    if (explicit) return explicit.replace(/^http/, 'ws');
    // mock mode default: same origin
    return `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`;
  })();

  for (const chatId of [
    scenarios.egfr.chat.id,
    scenarios.aspirin.chat.id,
    scenarios.aki1.chat.id,
  ]) {
    const url = `${wsBase}/ws/chat/${chatId}`;
    const server = new Server(url);
    server.on('connection', (socket) => {
      socket.on('message', (raw) => {
        try {
          const msg = JSON.parse(String(raw)) as { type: string };
          if (msg.type === 'ping') {
            socket.send(JSON.stringify({ type: 'pong' }));
          }
      if (msg.type === 'user_message' && chatId === scenarios.egfr.chat.id) {
            void playScript(socket, scenarios.egfr.script);
          }
        } catch {
          socket.send(JSON.stringify({ type: 'error', code: 'BAD_JSON' }));
        }
      });
    });
    servers.push(server);
  }

  return {
    servers,
    stop() {
      for (const s of servers) s.stop();
    },
  };
}
