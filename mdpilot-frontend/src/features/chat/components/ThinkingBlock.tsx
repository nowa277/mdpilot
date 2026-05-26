import { useEffect, useState } from 'react';

interface Props {
  reasoning: string;
  defaultOpen?: boolean;
}

export function ThinkingBlock({ reasoning, defaultOpen = true }: Props) {
  const [open, setOpen] = useState(defaultOpen);

  useEffect(() => {
    setOpen(defaultOpen);
  }, [defaultOpen]);

  return (
    <div className="thinking-block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="thinking-header"
      >
        <span className="thinking-label">Thinking</span>
        <span className="thinking-toggle">{open ? 'v' : '>'}</span>
        {!open && <span className="thinking-hint"></span>}
      </button>
      {open && (
        <div className="thinking-content whitespace-pre-wrap">
          {reasoning}
        </div>
      )}
    </div>
  );
}
