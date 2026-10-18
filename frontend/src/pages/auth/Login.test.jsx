import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const login = vi.fn(() => Promise.resolve());
vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({ login, isLoading: false }),
}));

let demo = { enabled: false, accounts: [] };
vi.mock('@/lib/demo', async (importOriginal) => ({
  ...(await importOriginal()),
  useDemoInfo: () => ({ data: demo }),
}));

const { Login } = await import('./Login');

describe('Login demo accounts', () => {
  beforeEach(() => login.mockClear());

  it('shows no demo panel on a normal deployment', () => {
    demo = { enabled: false, accounts: [] };
    render(<MemoryRouter><Login /></MemoryRouter>);
    expect(screen.queryByText('Try the live demo')).not.toBeInTheDocument();
  });

  it('signs in with one click as a shared demo account', async () => {
    demo = { enabled: true, accounts: [{ username: 'reviewer', role: 'REVIEWER' }], password: 'demo-pass' };
    render(<MemoryRouter><Login /></MemoryRouter>);
    fireEvent.click(screen.getByText('Sign in as reviewer'));
    await waitFor(() => expect(login).toHaveBeenCalledWith({ username: 'reviewer', password: 'demo-pass' }));
  });
});
