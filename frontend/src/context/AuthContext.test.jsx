import React from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import { AuthProvider, useAuth } from './AuthContext';
import { fetchApi } from '@/services/apiClient';

function Probe() {
  const { isAuthenticated, isLoading, sessionEnded } = useAuth();
  if (isLoading) return <p>loading</p>;
  return <p>{isAuthenticated ? 'signed in' : 'signed out'}{sessionEnded ? ', session ended' : ''}</p>;
}

afterEach(() => vi.unstubAllGlobals());

describe('AuthProvider', () => {
  it('signs out when the server reports the session has ended', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url) => url.endsWith('/auth/me')
      ? { ok: true, status: 200, json: async () => ({ username: 'ravi', role: 'REVIEWER' }) }
      : { ok: false, status: 401, json: async () => ({ detail: 'Session has been revoked' }) }));
    render(<AuthProvider><Probe /></AuthProvider>);
    await screen.findByText('signed in', {}, { timeout: 5000 });

    await act(async () => { await fetchApi('/documents').catch(() => {}); });
    await waitFor(() => expect(screen.getByText('signed out, session ended')).toBeInTheDocument(), { timeout: 5000 });
  });
});
