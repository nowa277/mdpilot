import type { ToolCardProps } from '../types';
import { AlphaFold2Card } from './AlphaFold2Card';
import { AmberCard } from './AmberCard';
import { BashCard } from './BashCard';
import { BioReasonCard } from './BioReasonCard';
import { DefaultCard } from './DefaultCard';

type ToolRenderer = React.ComponentType<ToolCardProps>;

interface ToolRendererRegistry {
  [toolName: string]: ToolRenderer;
}

const TOOL_RENDERERS: ToolRendererRegistry = {
  alphafold2_predict: AlphaFold2Card,
  bioreason_annotate: BioReasonCard,
  amber_minimize: AmberCard,
  amber_heat: AmberCard,
  amber_equilibrate: AmberCard,
  amber_production: AmberCard,
  bash_run: BashCard,
  ssh_bash: BashCard,
};

export function ToolCard({ tool }: ToolCardProps) {
  const Renderer = TOOL_RENDERERS[tool.name] || DefaultCard;
  return <Renderer tool={tool} />;
}
