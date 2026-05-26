import { cn } from '@shared/utils';
import { useState } from 'react';

import { useCopyToClipboard } from '../hooks/useCopyToClipboard';

interface Props {
  language: string;
  code: string;
  inline?: boolean;
  maxLines?: number;
}

export function EnhancedCodeBlock({
  language,
  code,
  inline = false,
  maxLines = 10,
}: Props) {
  const { copied, copy } = useCopyToClipboard();
  const [isExpanded, setIsExpanded] = useState(false);

  // Inline code directly returns
  if (inline) {
    return (
      <code className="rounded bg-code-bg px-1.5 py-0.5 text-sm font-mono">
        {code}
    </code>
    );
  }

  const lines = code.split('\n');
  const lineCount = lines.length;
  const shouldCollapse = lineCount > maxLines && !isExpanded;

  const handleCopy = () => {
    copy(code);
  };

  const handleExpand = () => {
    setIsExpanded(true);
  };

  return (
    <div className={cn('code-block', shouldCollapse && 'code-collapsed')}>
      {/* code block header */}
      <div className="code-header">
        <span className="code-language">{language || 'text'}</span>
        <div className="code-actions">
          <span className="code-lines">{lineCount} lines</span>
          <button
         type="button"
            onClick={handleCopy}
            className="code-copy-btn"
          >
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
      </div>

      {/* code block body */}
      <div className="code-body">
        {/* line numbers */}
        <div className="code-line-numbers">
          {lines.map((_, index) => (
            <div key={index + 1}>{index + 1}</div>
          ))}
     </div>

        {/* code-content */}
        <pre className="code-content">
          <code>{code}</code>
        </pre>
      </div>

      {/* expand button */}
      {shouldCollapse && (
        <div className="code-expand-overlay">
          <button
            type="button"
         onClick={handleExpand}
            className="code-expand-btn"
          >
            ▼ Expand all ({lineCount} lines)
          </button>
        </div>
      )}
    </div>
  );
}
