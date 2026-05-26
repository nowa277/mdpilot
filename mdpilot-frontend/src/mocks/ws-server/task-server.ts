import { Server } from 'mock-socket';

import { scenarios } from '../fixtures';

export interface TaskMockServers {
  servers: Server[];
  stop(): void;
}

export function startTaskMockServers(): TaskMockServers {
  const servers: Server[] = [];
  const wsBase = (() => {
    const explicit = import.meta.env.VITE_WS_BASE;
    if (explicit) return explicit.replace(/^http/, 'ws');
    return `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`;
  })();

  for (const task of scenarios.egfr.tasks) {
    const url = `${wsBase}/ws/task/${task.id}`;
    const server = new Server(url);
    server.on('connection', (socket) => {
      let pct = task.progress;
      const interval = setInterval(() => {
        pct = Math.min(100, pct + 2);
        socket.send(
          JSON.stringify({
        type: 'log_line',
            line: `[${task.id}] tick at ${pct}%`,
            level: 'info',
            ts: new Date().toISOString(),
          }),
        );
        socket.send(JSON.stringify({ type: 'progress', percent: pct, stage: task.kind }));
        if (pct >= 100) {
          socket.send(JSON.stringify({ type: 'status', status: 'succeeded' }));
          clearInterval(interval);
        }
      }, 1500);
      socket.on('close', () => clearInterval(interval));
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
