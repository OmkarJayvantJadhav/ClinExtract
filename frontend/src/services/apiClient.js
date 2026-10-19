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

// Called when the API answers 401: the session expired or was revoked (e.g. by an admin)
const sessionExpiredListeners = new Set();

/** Registers `listener` for an ended session; returns a function that unregisters it. */
export function onSessionExpired(listener) {
  sessionExpiredListeners.add(listener);
  return () => sessionExpiredListeners.delete(listener);
}

function checkSession(status) {
  if (status === 401) sessionExpiredListeners.forEach(listener => listener());
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
    checkSession(response.status);
    const errorData = await response.json().catch(() => ({}));
    const detail = errorData?.detail ?? errorData?.error;
    throw new ApiError(errorMessage(errorData, response.status), response.status, detail);
  }

  if (response.status === 204) return null;
  return await response.json();
}

/**
 * Uploads one document with real progress reporting (fetch cannot report upload progress).
 * Resolves with the created document; rejects with ApiError (e.g. status 409 with a
 * DUPLICATE_DOCUMENT detail when the same file was uploaded before).
 */
export function uploadDocument(file, { onProgress, allowDuplicate = false } = {}) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', apiUrl(`/documents${allowDuplicate ? '?allow_duplicate=true' : ''}`));
    xhr.withCredentials = true;
    xhr.setRequestHeader('X-CSRF-Token', getCsrfToken());
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      let body = {};
      try { body = JSON.parse(xhr.responseText || '{}'); } catch { /* non-JSON error page */ }
      if (xhr.status >= 200 && xhr.status < 300) return resolve(body);
      checkSession(xhr.status);
      reject(new ApiError(errorMessage(body, xhr.status), xhr.status, body?.detail));
    };
    xhr.onerror = () => reject(new ApiError('Cannot reach the server', 0));
    const form = new FormData();
    form.append('file', file);
    xhr.send(form);
  });
}
