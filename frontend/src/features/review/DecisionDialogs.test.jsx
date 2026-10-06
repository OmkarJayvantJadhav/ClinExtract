import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DecisionDialogs } from './DecisionDialogs';

const corrected = [{ id: 'f1', name: 'glucose', original: '9O', newValue: '90' }];
const warnings = [{ id: 'f2', name: 'hemoglobin', value: '19.1 g/dL', state: 'OUTSIDE_REFERENCE_RANGE' }];

describe('DecisionDialogs (approve)', () => {
  it('requires a reason per correction and acknowledgement of flagged values', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<DecisionDialogs open type="APPROVE" onOpenChange={() => {}} onSubmit={onSubmit} correctedFields={corrected} warnings={warnings} />);

    const approve = screen.getByRole('button', { name: 'Approve Document' });
    expect(approve).toBeDisabled();

    await user.type(screen.getByPlaceholderText(/OCR misread/), 'OCR read O as 0');
    expect(approve).toBeDisabled(); // still needs the acknowledgement

    await user.click(screen.getByRole('checkbox'));
    expect(approve).toBeEnabled();

    await user.click(approve);
    expect(onSubmit).toHaveBeenCalledWith({ reasons: { f1: 'OCR read O as 0' } });
  });

  it('approves immediately when there is nothing to justify', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<DecisionDialogs open type="APPROVE" onOpenChange={() => {}} onSubmit={onSubmit} />);
    await user.click(screen.getByRole('button', { name: 'Approve Document' }));
    expect(onSubmit).toHaveBeenCalledWith({ reasons: {} });
  });
});

describe('DecisionDialogs (reject)', () => {
  it('requires a rejection reason', () => {
    render(<DecisionDialogs open type="REJECT" onOpenChange={() => {}} onSubmit={() => {}} />);
    expect(screen.getByRole('button', { name: 'Confirm Rejection' })).toBeDisabled();
  });
});
