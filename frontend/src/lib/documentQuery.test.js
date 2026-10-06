import { describe, it, expect } from 'vitest';
import { buildDocumentQuery } from './documentQuery';

const parse = (url) => Object.fromEntries(new URL(url, 'http://x').searchParams);

describe('buildDocumentQuery', () => {
  it('includes only the filters that are set', () => {
    expect(parse(buildDocumentQuery({ page: 2 }))).toEqual({ page: '2', size: '25' });
    expect(parse(buildDocumentQuery({ q: '  smith ', status: 'ALL', page: 1 }))).toEqual({ page: '1', size: '25', q: 'smith' });
  });

  it('passes status and makes the end date inclusive', () => {
    const p = parse(buildDocumentQuery({ status: 'HUMAN_APPROVED', from: '2026-01-01', to: '2026-01-31', page: 1 }));
    expect(p.status).toBe('HUMAN_APPROVED');
    expect(p.created_from).toBe('2026-01-01T00:00:00Z');
    expect(p.created_to).toBe('2026-02-01T00:00:00.000Z');
  });

  it('encodes search terms safely', () => {
    expect(buildDocumentQuery({ q: 'a&b=c', page: 1 })).toContain('q=a%26b%3Dc');
  });
});
