// Foundation for API calls - connected to backend

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';

export const getCsrfToken = () => {
  const match = document.cookie.match(new RegExp('(^| )clinextract_csrf=([^;]+)'));
  if (match) return match[2];
  return '';
};

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
  return await fetchApi(`/audit?document_id=${documentId}&size=100`);
};

export async function fetchApi(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  
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

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      credentials: 'include',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || errorData.message || `API Error: ${response.status}`);
    }

    if (response.status === 204) return null;
    return await response.json();
  } catch (error) {
    console.error('API Request failed:', error);
    throw error;
  }
}
