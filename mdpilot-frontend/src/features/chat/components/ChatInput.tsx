import { Button } from '@shared/ui';
import { type KeyboardEvent, useEffect, useRef, useState } from 'react';
import { SkillSelector } from './SkillSelector';

interface Props {
  disabled?: boolean;
  isStreaming?: boolean;
  onSubmit: (content: string, activeSkills?: string[]) => void;
  onStop?: () => void;
}

export function ChatInput({ disabled, isStreaming, onSubmit, onStop }: Props) {
  const [value, setValue] = useState('');
  const [activeSkills, setActiveSkills] = useState<string[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea based on content
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = 'auto';
    const newHeight = Math.min(textarea.scrollHeight, 200);
    textarea.style.height = `${newHeight}px`;
  }, [value]);

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || isStreaming) return;
    onSubmit(trimmed, activeSkills.length > 0 ? activeSkills : undefined);
    setValue('');
    setActiveSkills([]);
  }

  function handleStop() {
    onStop?.();
  }

  const showStopButton = isStreaming && onStop;
  const canSubmit = !disabled && !isStreaming && value.trim() !== '';

  return (
    <div className="border-t border-border-1 bg-bg-1 p-4">
      <div className="mx-auto flex w-full max-w-[860px] flex-col gap-2">
        <SkillSelector selected={activeSkills} onChange={setActiveSkills} />
        <div className="flex gap-2">
          <div className="relative flex-1">
            <textarea
              ref={textareaRef}
              aria-label="Enter command for MDPilot"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={disabled}
              rows={1}
              placeholder={isStreaming ? 'generating reply…' : 'Enter command… (Shift+Enter for new line)'}
              className="w-full resize-none rounded-card border border-border-1 bg-bg-0 px-3 py-2 text-sm text-text-1 placeholder:text-text-3 focus-visible:border-accent-1 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60"
              style={{ minHeight: '40px', maxHeight: '200px' }}
            />
          </div>
          {showStopButton ? (
            <Button onClick={handleStop} variant="ghost">Stop</Button>
          ) : (
            <Button onClick={submit} disabled={!canSubmit}>Send</Button>
          )}
        </div>
      </div>
    </div>
  );
}
