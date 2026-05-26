import artifacts from './artifacts.json' with { type: 'json' };
import chat from './chat.json' with { type: 'json' };
import messages from './messages.json' with { type: 'json' };
import { buildEgfrScript } from './script';
import tasks from './tasks.json' with { type: 'json' };
import toolCalls from './tool-calls.json' with { type: 'json' };

export const egfrScenario = {
  chat,
  messages,
  tasks,
  artifacts,
  toolCalls,
  script: buildEgfrScript(),
};
