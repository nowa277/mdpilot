import { createWsClient, type WsClient, type WsMessage } from '@shared/ws';
import { useEffect, useRef, useState } from 'react';

export interface UseReconnectingWSResult {
  client: WsClient | null;
  state: WsClient['state'] | 'idle';
  send(msg: WsMessage): void;
}

export function useReconnectingWS(url: string | null): UseReconnectingWSResult {
  const clientRef = useRef<WsClient | null>(null);
  const [state, setState] = useState<WsClient['state'] | 'idle'>('idle');

  useEffect(() => {
    if (!url) {
      clientRef.current = null;
      setState('idle');
      return;
    }
    const client = createWsClient(url);
    clientRef.current = client;
    setState('connecting');
    const unsubOpen = client.on('__open__', () => setState('open'));
    const tick = setInterval(() => setState(client.state), 250);
    return () => {
      unsubOpen();
      clearInterval(tick);
      client.close();
      clientRef.current = null;
    };
  }, [url]);

  return {
    client: clientRef.current,
    state,
    send(msg) {
      clientRef.current?.send(msg);
    },
  };
}
