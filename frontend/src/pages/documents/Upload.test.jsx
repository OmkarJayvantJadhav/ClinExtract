import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('@/lib/demo', () => ({ useDemoInfo: () => ({ data: { enabled: false } }), SAMPLE_REPORTS: [] }));
const { Upload } = await import('./Upload');

describe('Upload', () => {
  it('opens the file picker from the keyboard', () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><Upload /></MemoryRouter></QueryClientProvider>);
    const input = document.getElementById('file-upload');
    const click = vi.spyOn(input, 'click');
    const zone = screen.getByRole('button', { name: 'Choose files to upload' });
    zone.focus();
    fireEvent.keyDown(zone, { key: 'Enter' });
    expect(click).toHaveBeenCalled();
  });
});
