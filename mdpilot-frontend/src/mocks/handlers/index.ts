import { artifactHandlers } from './artifacts';
import { chatHandlers } from './chats';
import { healthHandlers } from './health';
import { nodeHandlers } from './nodes';

export const restHandlers = [
  ...healthHandlers,
  ...chatHandlers,
  ...artifactHandlers,
  ...nodeHandlers,
];
