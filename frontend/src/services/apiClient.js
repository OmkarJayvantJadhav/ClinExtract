// Foundation for API calls - connected to backend

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';

// Validation states that make a value unusable; they must be corrected before approval.
// Keep in sync with BLOCKING_STATES in backend/src/validation/engine.py.
export const BLOCKING_STATES = ['MISSING', 'INVALID_FORMAT', 'IMPLAUSIBLE_VALUE'];

export const getCsrfToken = () => {
  const match = document.cookie.match(new RegExp('(^| )clinextract_csrf=([^;]+)'));
  if (match) return match[2];
  return '';
};

export const apiUrl = (endpoint) => `${API_BASE_URL}${endpoint}`;

export const getAnalytics = async () => {
  return await fetchApi('/analytics/metrics');
};

export const getDetailedHealth = async () => {
  return await fetchApi('/health/detailed');
};

export const getAuditLogs = async (params = {}) => {
  const urlParams = new URLSearchParams();
  Object.keys(params).forEach(key => {
    if (params[key]) urlParams.append(key, params[key]);
  });
  const queryString = urlParams.toString();
  return await fetchApi(`/audit${queryString ? '?' + queryString : ''}`);
};

export const getDocumentAudit = async (documentId) => {
  return await fetchApi(`/audit?document_id=${encodeURIComponent(documentId)}&size=100`);
};

export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

function errorMessage(errorData, status) {
  const detail = errorData?.detail ?? errorData?.error?.message ?? errorData?.message;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object' && detail.message) return detail.message;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg; // FastAPI request validation
  return `API Error: ${status}`;
}

/**
 * fetch wrapper. `endpoint` is relative to API_BASE_URL (which already includes /api/v1),
 * e.g. fetchApi('/documents'). Throws ApiError with `.status` and `.detail` on failure.
 */
export async function fetchApi(endpoint, options = {}) {
  const url = apiUrl(endpoint);

  const headers = { ...options.headers };

  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  } else {
    delete headers['Content-Type'];
  }

  // Inject CSRF token for mutations
  const method = (options.method || 'GET').toUpperCase();
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    headers['X-CSRF-Token'] = getCsrfToken();
  }

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const detail = errorData?.detail ?? errorData?.error;
    throw new ApiError(errorMessage(errorData, response.status), response.status, detail);
  }

  if (response.status === 204) return null;
  return await response.json();
}
