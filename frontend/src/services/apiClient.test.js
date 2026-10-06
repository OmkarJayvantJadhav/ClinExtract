import { describe, it, expect, vi, afterEach } from 'vitest';
import { fetchApi, ApiError, apiUrl } from './apiClient';

function mockFetch(status, body) {
  const fn = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  });
  vi.stubGlobal('fetch', fn);
  return fn;
}

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = 'clinextract_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT';
});

describe('fetchApi', () => {
  it('prefixes the API base URL exactly once', async () => {
    const fetch = mockFetch(200, { ok: true });
    await fetchApi('/documents');
    expect(fetch.mock.calls[0][0]).toBe(apiUrl('/documents'));
    expect(fetch.mock.calls[0][0]).not.toMatch(/api\/v1\/api\/v1/);
  });

  it('sends cookies and the CSRF token on mutations only', async () => {
    document.cookie = 'clinextract_csrf=tok123';
    const fetch = mockFetch(200, {});
    await fetchApi('/reviews/x/claim', { method: 'POST' });
    await fetchApi('/documents');
    expect(fetch.mock.calls[0][1].headers['X-CSRF-Token']).toBe('tok123');
    expect(fetch.mock.calls[0][1].credentials).toBe('include');
    expect(fetch.mock.calls[1][1].headers['X-CSRF-Token']).toBeUndefined();
  });

  it('throws ApiError with status and structured detail', async () => {
    mockFetch(422, { detail: { code: 'UNRESOLVED_VALIDATION_ISSUES', message: 'Fix fields', fields: [{ field_name: 'glucose' }] } });
    const err = await fetchApi('/reviews/x/complete', { method: 'POST' }).catch(e => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(err.message).toBe('Fix fields');
    expect(err.detail.fields[0].field_name).toBe('glucose');
  });

  it('uses string details and FastAPI validation messages', async () => {
    mockFetch(409, { detail: 'DOCUMENT_ALREADY_CLAIMED' });
    expect((await fetchApi('/x').catch(e => e)).message).toBe('DOCUMENT_ALREADY_CLAIMED');
    mockFetch(422, { detail: [{ msg: 'field required' }] });
    expect((await fetchApi('/x').catch(e => e)).message).toBe('field required');
  });

  it('returns null for 204 responses', async () => {
    mockFetch(204, null);
    expect(await fetchApi('/documents/x?reason=abc', { method: 'DELETE' })).toBeNull();
  });
});
