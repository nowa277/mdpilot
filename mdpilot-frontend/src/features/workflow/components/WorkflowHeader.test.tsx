import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { WorkflowHeader } from './WorkflowHeader';

describe('WorkflowHeader', () => {
  it('renders total tools count', () => {
    render(
      <WorkflowHeader
        total={10}
        completed={3}
        running={2}
        failed={1}
      />
    );
    expect(screen.getByText('Total: 10')).toBeInTheDocument();
  });

  it('renders completed count with green styling', () => {
    render(
      <WorkflowHeader
        total={10}
        completed={5}
        running={2}
        failed={1}
      />
    );
    const completedElement = screen.getByText('Completed: 5');
    expect(completedElement).toBeInTheDocument();
    expect(completedElement).toHaveClass('text-green-600');
  });

  it('renders running count with yellow styling', () => {
    render(
      <WorkflowHeader
      total={10}
        completed={3}
      running={4}
        failed={1}
      />
    );
    const runningElement = screen.getByText('Running: 4');
    expect(runningElement).toBeInTheDocument();
    expect(runningElement).toHaveClass('text-yellow-600');
  });

  it('renders failed count with red styling', () => {
    render(
      <WorkflowHeader
        total={10}
     completed={3}
        running={2}
        failed={2}
      />
    );
    const failedElement = screen.getByText('Failed: 2');
    expect(failedElement).toBeInTheDocument();
  expect(failedElement).toHaveClass('text-red-600');
  });

  it('renders all statistics together', () => {
    render(
      <WorkflowHeader
        total={20}
    completed={10}
        running={5}
        failed={3}
      />
    );
    expect(screen.getByText('Total: 20')).toBeInTheDocument();
    expect(screen.getByText('Completed: 10')).toBeInTheDocument();
    expect(screen.getByText('Running: 5')).toBeInTheDocument();
    expect(screen.getByText('Failed: 3')).toBeInTheDocument();
  });
});
