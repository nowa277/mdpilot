import type { ScriptStep } from '../fixtures/scenario-egfr-erlotinib/script';

export interface SocketLike {
  send(data: string): void;
}

export async function playScript(socket: SocketLike, steps: ScriptStep[]): Promise<void> {
  for (const step of steps) {
    await new Promise((resolve) => setTimeout(resolve, step.delayMs));
    socket.send(JSON.stringify(step.event));
  }
}
