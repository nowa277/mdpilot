import { aki1Scenario } from './scenario-1aki-md';
import { aspirinScenario } from './scenario-aspirin-cox2';
import { egfrScenario } from './scenario-egfr-erlotinib';

export const scenarios = {
  egfr: egfrScenario,
  aspirin: aspirinScenario,
  aki1: aki1Scenario,
};

export const allChats = [egfrScenario.chat, aspirinScenario.chat, aki1Scenario.chat];
export const allMessages = [
  ...egfrScenario.messages,
  ...aspirinScenario.messages,
  ...aki1Scenario.messages,
];
export const allTasks = [...egfrScenario.tasks];
export const allArtifacts = [...egfrScenario.artifacts];
