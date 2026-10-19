import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { apiUrl, getCsrfToken, onSessionExpired } from '@/services/apiClient';
import { queryClient } from '@/lib/queryClient';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  // True after the server ended the session (expired, revoked, account changed)
  const [sessionEnded, setSessionEnded] = useState(false);

  const checkSession = useCallback(async () => {
    try {
      const response = await fetch(apiUrl('/auth/me'), {
        headers: { 'Accept': 'application/json' },
        credentials: 'include'
      });
      if (response.ok) {
        const data = await response.json();
        setUser(data);
        setIsAuthenticated(true);
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }
    } catch (error) {
      console.error('Session check failed', error);
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkSession();
  }, [checkSession]);

  // Any API call answered 401: sign out locally, so the app returns to the sign-in page
  // instead of showing errors on every page (and polling with a dead session)
  const signedIn = useRef(false);
  useEffect(() => { signedIn.current = isAuthenticated; }, [isAuthenticated]);
  useEffect(() => onSessionExpired(() => {
    queryClient.clear();
    if (signedIn.current) setSessionEnded(true);
    setUser(null);
    setIsAuthenticated(false);
  }), []);

  const login = useCallback(async (credentials) => {
    setIsLoading(true);
    try {
      const response = await fetch(apiUrl('/auth/login'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'X-CSRF-Token': getCsrfToken()
        },
        body: JSON.stringify(credentials),
        credentials: 'include'
      });
      
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        const detail = typeof body.detail === 'string' ? body.detail : null;
        if (response.status === 401) throw new Error('Invalid username or password');
        // 429: rate limited or account locked; the server explains which
        throw new Error(detail || `Login failed (${response.status})`);
      }
      // Never show one user's cached data to the next
      queryClient.clear();
      
      const data = await response.json();
      setUser(data);
      setSessionEnded(false);
      setIsAuthenticated(true);
    } catch (error) {
      console.error('Login error', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await fetch(apiUrl('/auth/logout'), { 
        method: 'POST',
        headers: {
          'X-CSRF-Token': getCsrfToken()
        },
        credentials: 'include' 
      });
    } catch (err) {
      console.error('Logout error', err);
    }
    queryClient.clear();
    setUser(null);
    setIsAuthenticated(false);
  }, []);

  const hasRole = useCallback((roles) => {
    if (!user || !user.role) return false;
    if (Array.isArray(roles)) {
      return roles.includes(user.role);
    }
    return user.role === roles;
  }, [user]);

  const value = {
    user,
    isAuthenticated,
    isLoading,
    sessionEnded,
    login,
    logout,
    hasRole
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
