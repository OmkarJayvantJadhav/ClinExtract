import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

let role = 'VIEWER';
vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({
    hasRole: (roles) => (Array.isArray(roles) ? roles.includes(role) : roles === role),
  }),
}));

const { Sidebar } = await import('./Sidebar');

function renderAs(r) {
  role = r;
  return render(<MemoryRouter><Sidebar collapsed={false} /></MemoryRouter>);
}

describe('Sidebar role filtering', () => {
  it('hides admin and reviewer pages from viewers', () => {
    renderAs('VIEWER');
    expect(screen.getByText('Documents')).toBeInTheDocument();
    for (const hidden of ['Upload', 'Review Queue', 'Analytics', 'Audit Logs', 'Users']) {
      expect(screen.queryByText(hidden)).not.toBeInTheDocument();
    }
  });

  it('shows the review queue to reviewers but not admin pages', () => {
    renderAs('REVIEWER');
    expect(screen.getByText('Review Queue')).toBeInTheDocument();
    expect(screen.queryByText('Users')).not.toBeInTheDocument();
  });

  it('shows everything to admins', () => {
    renderAs('ADMIN');
    for (const item of ['Upload', 'Review Queue', 'Analytics', 'Audit Logs', 'Users', 'Settings']) {
      expect(screen.getByText(item)).toBeInTheDocument();
    }
  });
});
