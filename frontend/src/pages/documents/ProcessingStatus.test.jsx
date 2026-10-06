import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ProcessingStatus } from './ProcessingStatus';

describe('ProcessingStatus', () => {
  it('describes the final outcome', () => {
    render(<ProcessingStatus currentStatus="HUMAN_REJECTED" />);
    expect(screen.getByText('Rejected by a reviewer')).toBeInTheDocument();
  });

  it('shows a failure at the processing stage', () => {
    render(<ProcessingStatus currentStatus="FAILED" />);
    expect(screen.getByText('Processing failed')).toBeInTheDocument();
    expect(screen.queryByText('Document finalized')).toBeInTheDocument(); // later stage still pending
  });

  it('treats an in-progress review as the review stage', () => {
    render(<ProcessingStatus currentStatus="REVIEW_IN_PROGRESS" />);
    expect(screen.getByText('Human validation (if required)')).toBeInTheDocument();
  });
});
