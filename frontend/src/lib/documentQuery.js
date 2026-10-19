export const PAGE_SIZE = 25;

function filterParams({ q, status, from, to }) {
  const params = new URLSearchParams();
  if (q?.trim()) params.set('q', q.trim());
  if (status && status !== 'ALL') params.set('status', status);
  // Days in the user's time zone, as the table shows upload dates
  if (from) params.set('created_from', new Date(`${from}T00:00:00`).toISOString());
  if (to) {
    // inclusive end date: everything before the following midnight
    const end = new Date(`${to}T00:00:00`);
    end.setDate(end.getDate() + 1);
    params.set('created_to', end.toISOString());
  }
  return params;
}

/** Builds the /documents list URL for the Library's search, filters and paging. */
export function buildDocumentQuery({ q, status, from, to, page, size = PAGE_SIZE }) {
  const params = new URLSearchParams({ page: String(page), size: String(size) });
  for (const [key, value] of filterParams({ q, status, from, to })) params.set(key, value);
  return `/documents?${params.toString()}`;
}

/**
 * Export URL for the same filters. With no status filter the server exports final documents
 * (auto-accepted or approved by a reviewer).
 */
export function buildExportQuery(filters, format) {
  const params = filterParams(filters);
  params.set('format', format);
  return `/documents/export?${params.toString()}`;
}
