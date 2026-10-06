// Roles allowed to open each route. Routes not listed are available to every signed-in user.
// Mirrors the backend's require_roles(...) checks so users aren't shown pages that would 403.
export const ROUTE_ROLES = {
  '/documents/upload': ['ADMIN', 'OPERATOR'],
  '/review': ['ADMIN', 'REVIEWER'],
  '/analytics': ['ADMIN'],
  '/audit': ['ADMIN'],
  '/users': ['ADMIN'],
};
