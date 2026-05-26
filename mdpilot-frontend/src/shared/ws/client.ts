export interface WsMessage<T = unknown> {
  type: string;
  payload?: T;
  [key: string]: unknown;
}

export interface WsClientOptions {
  initialBackoffMs?: number;
  maxBackoffMs?: number;
  heartbeatMs?: number;
}

export interface WsClient {
  on(type: string, handler: (msg: WsMessage) => void): () => void;
  send(msg: WsMessage): void;
  close(): void;
  readonly state: 'connecting' | 'open' | 'closing' | 'closed';
}

export function createWsClient(url: string, options: WsClientOptions = {}): WsClient {
  const initial = options.initialBackoffMs ?? 500;
  const max = options.maxBackoffMs ?? 10_000;
  const heartbeat = options.heartbeatMs ?? 25_000;

  let socket: WebSocket | null = null;
  let backoff = initial;
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let closed = false;
  let state: WsClient['state'] = 'connecting';
  const handlers = new Map<string, Set<(msg: WsMessage) => void>>();

  function emit(type: string, msg: WsMessage): void {
    handlers.get(type)?.forEach((h) => h(msg));
  }

  function connect(): void {
    if (closed) return;
    state = 'connecting';
    socket = new WebSocket(url);

    socket.onopen = () => {
      state = 'open';
      backoff = initial;
      heartbeatTimer = setInterval(() => {
        socket?.send(JSON.stringify({ type: 'ping' }));
      }, heartbeat);
    };

    socket.onmessage = (event) => {
      try {
      const msg = JSON.parse(String(event.data)) as WsMessage;
     if (typeof msg.type !== 'string') throw new Error('message missing type');
        emit(msg.type, msg);
      } catch (err) {
        emit('error', { type: 'error', payload: err });
      }
    };

    socket.onerror = () => {
      emit('error', { type: 'error', payload: new Error('socket error') });
    };

    socket.onclose = () => {
      if (heartbeatTimer) clearInterval(heartbeatTimer);
      heartbeatTimer = null;
      state = 'closed';
      socket = null;
      if (closed) return;
      reconnectTimer = setTimeout(() => {
    backoff = Math.min(backoff * 2, max);
        connect();
      }, backoff);
    };
  }

  connect();

  return {
    on(type, handler) {
      let set = handlers.get(type);
      if (!set) {
      set = new Set();
        handlers.set(type, set);
      }
    set.add(handler);
      return () => set?.delete(handler);
    },
    send(msg) {
      if (socket && state === 'open') {
        socket.send(JSON.stringify(msg));
      }
    },
    close() {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (heartbeatTimer) clearInterval(heartbeatTimer);
      state = 'closing';
      socket?.close();
    },
    get state() {
   return state;
    },
  };
}
