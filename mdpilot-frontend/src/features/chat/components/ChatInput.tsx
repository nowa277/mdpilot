import { Button } from '@shared/ui';
import { cn } from '@shared/utils';
import { type KeyboardEvent, useEffect, useRef, useState } from 'react';
import { SlashCommandMenu } from './SlashCommandMenu';
import type { SkillInfo } from '@shared/types/api.gen';

interface Props {
  disabled?: boolean;
  isStreaming?: boolean;
  onSubmit: (content: string, activeSkills?: string[]) => void;
  onStop?: () => void;
}

function parseSlashCommand(input: string): { command: string | null; prompt: string } {
  if (!input.startsWith('/')) return { command: null, prompt: input };
  const spaceIdx = input.indexOf(' ');
  if (spaceIdx === -1) return { command: input.slice(1), prompt: '' };
  return { command: input.slice(1, spaceIdx), prompt: input.slice(spaceIdx + 1) };
}

export function ChatInput({ disabled, isStreaming, onSubmit, onStop }: Props) {
  const [value, setValue] = useState('');
  const [slashFilter, setSlashFilter] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  }, [value]);

  useEffect(() => {
    if (value.startsWith('/')) {
      setSlashFilter(value.split(' ')[0]);
    } else {
      setSlashFilter(null);
    }
  }, [value]);

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (slashFilter !== null && ['ArrowUp', 'ArrowDown', 'Tab'].includes(e.key)) {
      e.preventDefault();
      return;
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || isStreaming) return;
    const { command, prompt } = parseSlashCommand(trimmed);
    const skills = command ? [command] : undefined;
    onSubmit(prompt || trimmed, skills);
    setValue('');
    setSlashFilter(null);
    setPanelOpen(false);
  }

  function handleSkillSelect(skill: SkillInfo) {
    setValue(skill.command + ' ');
    setSlashFilter(null);
    setPanelOpen(false);
    textareaRef.current?.focus();
  }

  const showStopButton = isStreaming && onStop;
  const canSubmit = !disabled && !isStreaming && value.trim() !== '';

  return (
    <div className="border-t border-border-1 bg-bg-1 p-4">
      <div className="mx-auto flex w-full max-w-[860px] flex-col gap-2">
        <div className="relative">
          {slashFilter !== null && (
            <SlashCommandMenu
              mode="slash"
              filter={slashFilter}
              onSelect={handleSkillSelect}
              onClose={() => setSlashFilter(null)}
            />
          )}
          {panelOpen && (
            <SlashCommandMenu
              mode="panel"
              filter=""
              onSelect={handleSkillSelect}
              onClose={() => setPanelOpen(false)}
            />
          )}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setPanelOpen(!panelOpen)}
              className={cn(
                'flex h-[40px] w-[40px] shrink-0 items-center justify-center rounded-card border transition-colors',
                panelOpen
                  ? 'border-accent-1/40 bg-accent-1/6 text-accent-1'
                  : 'border-border-1 text-text-2 hover:border-border-2 hover:bg-bg-2 hover:text-text-1',
              )}
            >
              +
            </button>
            <textarea
              ref={textareaRef}
              aria-label="给 MDPilot 输入指令"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={disabled}
              rows={1}
              placeholder={isStreaming ? '正在生成回复…' : '输入指令… (Shift+Enter 换行, / 斜杠命令)'}
              className="w-full resize-none rounded-card border border-border-1 bg-bg-0 px-3 py-2 text-sm text-text-1 placeholder:text-text-3 focus-visible:border-accent-1 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60"
              style={{ minHeight: '40px', maxHeight: '200px' }}
            />
          </div>
        </div>
        <div className="flex justify-end">
          {showStopButton ? (
            <Button onClick={onStop} variant="ghost">Stop</Button>
          ) : (
            <Button onClick={submit} disabled={!canSubmit}>Send</Button>
          )}
        </div>
      </div>
    </div>
  );
}
