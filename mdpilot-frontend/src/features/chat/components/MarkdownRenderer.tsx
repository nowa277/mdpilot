import 'highlight.js/styles/github-dark.css';

import { memo } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeHighlight from 'rehype-highlight';
import remarkGfm from 'remark-gfm';

import { EnhancedCodeBlock } from './EnhancedCodeBlock';

interface Props {
  source: string;
}

export const MarkdownRenderer = memo(function MarkdownRenderer({ source }: Props) {
  return (
    <div className="prose prose-invert max-w-none break-words text-text-1">
      <ReactMarkdown
      remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
     skipHtml
        components={{
          code({ node, inline, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || '');
            const language = match ? match[1] : '';
            const codeString = String(children).replace(/\n$/, '');

     return !inline ? (
              <EnhancedCodeBlock
                language={language}
                code={codeString}
                inline={false}
              />
            ) : (
              <code className={className} {...props}>
          {children}
           </code>
            );
      },
        }}
      >
        {source}
      </ReactMarkdown>
    </div>
  );
});
