import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { MarkdownRenderer } from './MarkdownRenderer';

describe('MarkdownRenderer', () => {
  it('renders heading and paragraph', () => {
    render(<MarkdownRenderer source={'# Hello\n\nWorld'} />);
    expect(screen.getByRole('heading', { name: 'Hello' })).toBeInTheDocument();
    expect(screen.getByText('World')).toBeInTheDocument();
  });

  it('escapes raw HTML to prevent XSS', () => {
    render(<MarkdownRenderer source={'<img src=x onerror="alert(1)">'} />);
    expect(document.querySelector('img')).toBeNull();
  });

  it('renders fenced code block with language class', () => {
    render(<MarkdownRenderer source={'```ts\nconst a = 1;\n```'} />);
    const code = document.querySelector('code');
    expect(code?.className).toMatch(/language-ts/);
  });
});
