import { describe, it, expect } from 'vitest';
import { buildDocumentQuery, buildExportQuery } from './documentQuery';

const parse = (url) => Object.fromEntries(new URL(url, 'http://x').searchParams);

describe('buildDocumentQuery', () => {
  it('includes only the filters that are set', () => {
    expect(parse(buildDocumentQuery({ page: 2 }))).toEqual({ page: '2', size: '25' });
    expect(parse(buildDocumentQuery({ q: '  smith ', status: 'ALL', page: 1 }))).toEqual({ page: '1', size: '25', q: 'smith' });
  });

  it('passes status and makes the end date inclusive', () => {
    const p = parse(buildDocumentQuery({ status: 'HUMAN_APPROVED', from: '2026-01-01', to: '2026-01-31', page: 1 }));
    expect(p.status).toBe('HUMAN_APPROVED');
    expect(p.created_from).toBe(new Date('2026-01-01T00:00:00').toISOString());
    expect(p.created_to).toBe(new Date('2026-02-01T00:00:00').toISOString());
  });

  it('uses the days of the user\'s time zone, as the table shows them', () => {
    const tz = process.env.TZ;
    process.env.TZ = 'Asia/Kolkata';
    try {
      // 19 Oct in India runs from 18:30 UTC the day before
      const p = parse(buildDocumentQuery({ from: '2026-10-19', to: '2026-10-19', page: 1 }));
      expect(p.created_from).toBe('2026-10-18T18:30:00.000Z');
      expect(p.created_to).toBe('2026-10-19T18:30:00.000Z');
    } finally {
      process.env.TZ = tz;
    }
  });

  it('encodes search terms safely', () => {
    expect(buildDocumentQuery({ q: 'a&b=c', page: 1 })).toContain('q=a%26b%3Dc');
  });
});

describe('buildExportQuery', () => {
  it('uses the same filters and the requested format', () => {
    const url = buildExportQuery({ q: ' jane ', status: 'HUMAN_APPROVED', from: '2026-01-01', to: '' }, 'csv');
    const from = encodeURIComponent(new Date('2026-01-01T00:00:00').toISOString());
    expect(url).toBe(`/documents/export?q=jane&status=HUMAN_APPROVED&created_from=${from}&format=csv`);
  });

  it('leaves the status to the server default when not filtered', () => {
    expect(buildExportQuery({ status: 'ALL' }, 'json')).toBe('/documents/export?format=json');
  });
});
