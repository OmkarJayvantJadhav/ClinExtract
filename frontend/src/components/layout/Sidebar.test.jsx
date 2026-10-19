import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
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

describe('Sidebar on small screens', () => {
  it('is hidden until opened, and closes when a page is picked', () => {
    role = 'VIEWER';
    const onClose = vi.fn();
    const { container, rerender } = render(<MemoryRouter><Sidebar collapsed={false} /></MemoryRouter>);
    expect(container.querySelector('aside').className).toContain('max-md:hidden');

    rerender(<MemoryRouter><Sidebar collapsed={false} mobileOpen onClose={onClose} /></MemoryRouter>);
    expect(container.querySelector('aside').className).not.toContain('max-md:hidden');
    fireEvent.click(screen.getByText('Documents'));
    expect(onClose).toHaveBeenCalled();
  });
});
