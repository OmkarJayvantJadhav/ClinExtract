import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// What the API answers; a plain function (a vi.fn returning a rejected promise is reported by
// Vitest as a test failure even though the page handles it)
let respond = async () => ({ total: 0, items: [] });
const calls = [];
vi.mock('@/services/apiClient', () => ({
  getAuditLogs: (params) => { calls.push(params); return respond(params); },
}));
const { AuditLogs } = await import('./AuditLogs');

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><AuditLogs /></QueryClientProvider>);
}

describe('AuditLogs', () => {
  it('pages through every event, not just the newest ones', async () => {
    respond = async () => ({ total: 250, items: [{ id: 'e1', created_at: '2026-10-19T10:00:00Z', action: 'DOCUMENT_VIEWED' }] });
    renderPage();
    expect(await screen.findByText('Page 1 of 3')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('Next page'));
    await waitFor(() => expect(calls.at(-1)).toEqual({ page: 2, size: 100 }));
  });

  it('shows a failure instead of "No logs found"', async () => {
    respond = async () => { throw new Error('Cannot reach the server'); };
    renderPage();
    expect(await screen.findByText('Cannot reach the server')).toBeInTheDocument();
    expect(screen.queryByText('No logs found')).not.toBeInTheDocument();
  });
});
