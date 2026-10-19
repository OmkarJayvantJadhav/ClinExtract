import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { EditableField } from './EditableField';
import { ConfirmWarningsDialog } from './DecisionDialogs';

const glucose = { id: 'g', name: 'glucose', value: '5.5', unit: '', isNumeric: true, state: 'UNRECOGNIZED_UNIT' };

function renderEditing(field, onEdit) {
  render(<EditableField field={field} currentValue={field.value} currentUnit={field.unit} isEditing
    onEditingChange={() => {}} onSelect={() => {}} onEdit={onEdit} />);
}

describe('EditableField', () => {
  it('lets a reviewer correct only the unit of a lab result', async () => {
    const user = userEvent.setup();
    const onEdit = vi.fn();
    renderEditing(glucose, onEdit);
    await user.type(screen.getByLabelText('Unit'), 'mmol/L{Enter}');
    expect(onEdit).toHaveBeenCalledWith('5.5', 'mmol/L');
  });

  it('offers no unit for fields without one', () => {
    renderEditing({ id: 'n', name: 'patient name', value: 'Ravi Kumar', unit: '', isNumeric: false }, () => {});
    expect(screen.queryByLabelText('Unit')).toBeNull();
  });

  it('treats an unchanged value and unit as a revert', async () => {
    const user = userEvent.setup();
    const onEdit = vi.fn();
    renderEditing({ ...glucose, unit: 'mg/dL' }, onEdit);
    await user.type(screen.getByLabelText('Value'), '{Enter}');
    expect(onEdit).toHaveBeenCalledWith(undefined);
  });
});

describe('ConfirmWarningsDialog', () => {
  it('shows the warnings and approves only once they are checked', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    const fields = [{ field_id: 'g', field_name: 'glucose', state: 'EXTREME_VALUE', messages: ['Value 9200 mg/dL is outside any plausible result'] }];
    render(<ConfirmWarningsDialog open fields={fields} onConfirm={onConfirm} onCancel={() => {}} />);
    expect(screen.getByText(/9200 mg\/dL is outside any plausible result/)).toBeInTheDocument();
    const approve = screen.getByRole('button', { name: 'Approve Document' });
    expect(approve).toBeDisabled();
    await user.click(screen.getByRole('checkbox'));
    await user.click(approve);
    expect(onConfirm).toHaveBeenCalled();
  });
});
