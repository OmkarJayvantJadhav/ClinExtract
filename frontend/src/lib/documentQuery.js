export const PAGE_SIZE = 25;

/** Builds the /documents list URL for the Library's search, filters and paging. */
export function buildDocumentQuery({ q, status, from, to, page, size = PAGE_SIZE }) {
  const params = new URLSearchParams({ page: String(page), size: String(size) });
  if (q?.trim()) params.set('q', q.trim());
  if (status && status !== 'ALL') params.set('status', status);
  if (from) params.set('created_from', `${from}T00:00:00Z`);
  if (to) {
    // inclusive end date: everything before the following midnight
    const end = new Date(`${to}T00:00:00Z`);
    end.setUTCDate(end.getUTCDate() + 1);
    params.set('created_to', end.toISOString());
  }
  return `/documents?${params.toString()}`;
}
