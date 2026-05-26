import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ResponseContent } from './ResponseContent';

describe('ResponseContent', () => {
  it('renders markdown content', () => {
    const content = `# Hello

This is a **bold** paragraph.`;
    render(<ResponseContent content={content} />);
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
    expect(screen.getByText('bold')).toBeInTheDocument();
  });

  it('renders code blocks with syntax highlighting', () => {
    const content = `\`\`\`typescript
const x = 42;
\`\`\``;
    render(<ResponseContent content={content} />);
    const code = document.querySelector('code');
    expect(code).toBeInTheDocument();
    expect(code?.className).toMatch(/language-typescript/);
  });

  it('escapes raw HTML to prevent XSS', () => {
    render(<ResponseContent content='<img src=x onerror="alert(1)">' />);
    expect(document.querySelector('img')).toBeNull();
  });

  it('renders lists', () => {
    const content = `- Item 1
- Item 2`;
    render(<ResponseContent content={content} />);
    expect(screen.getByText('Item 1')).toBeInTheDocument();
    expect(screen.getByText('Item 2')).toBeInTheDocument();
  });
});
