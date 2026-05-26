import 'highlight.js/styles/github-dark.css';
import 'katex/dist/katex.min.css';

import { memo } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeHighlight from 'rehype-highlight';
import rehypeKatex from 'rehype-katex';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';

interface Props {
  content: string;
}

export const ResponseContent = memo(function ResponseContent({ content }: Props) {
  return (
    <div className="prose prose-invert max-w-none break-words text-text-1">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeHighlight, rehypeKatex]}
        skipHtml
      >
        {content}
      </ReactMarkdown>
    </div>
  );
});
