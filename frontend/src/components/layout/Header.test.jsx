import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

const logout = vi.fn(() => Promise.resolve());
vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({ user: { username: 'ravi', role: 'REVIEWER' }, logout }),
}));

const { Header } = await import('./Header');

describe('Header', () => {
  it('shows who is signed in and signs out', async () => {
    render(
      <MemoryRouter initialEntries={['/documents']}>
        <Routes>
          <Route path="/documents" element={<Header toggleSidebar={() => {}} />} />
          <Route path="/login" element={<p>login page</p>} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText('ravi')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /sign out/i }));
    expect(await screen.findByText('login page')).toBeInTheDocument();
    expect(logout).toHaveBeenCalled();
  });
});
