import React from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppShell } from '@/components/layout/AppShell';
import { useAuth } from '@/context/AuthContext';
import { ROUTE_ROLES } from '@/routes/roles';

// Pages
import { Login } from '@/pages/auth/Login';
import { Dashboard } from '@/pages/dashboard/Dashboard';
import { Upload } from '@/pages/documents/Upload';
import { Library } from '@/pages/documents/Library';
import { DocumentDetails } from '@/pages/documents/DocumentDetails';
import { ReviewQueue } from '@/pages/review/ReviewQueue';
import { Workspace } from '@/pages/review/Workspace';
import { Analytics } from '@/pages/analytics/Analytics';
import { AuditLogs } from '@/pages/audit/AuditLogs';
import { SystemHealth } from '@/pages/health/SystemHealth';
import { UserManagement } from '@/pages/admin/UserManagement';
import { Settings } from '@/pages/admin/Settings';

function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div className="flex h-screen w-full items-center justify-center">Loading session...</div>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return children;
}

function RoleRoute({ path, children }) {
  const { hasRole } = useAuth();
  const roles = ROUTE_ROLES[path];
  if (roles && !hasRole(roles)) {
    return (
      <div className="p-8">
        <h1 className="text-2xl font-semibold">Access denied</h1>
        <p className="text-muted-foreground mt-2">Your role does not have access to this page.</p>
      </div>
    );
  }
  return children;
}

const guard = (path, element) => <RoleRoute path={path}>{element}</RoleRoute>;

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <Login />,
  },
  {
    path: '/review/workspace/:id',
    element: (
      <ProtectedRoute>
        <Workspace />
      </ProtectedRoute>
    )
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppShell />
      </ProtectedRoute>
    ),
    errorElement: (
      <div className="flex h-screen items-center justify-center p-4">
        <div className="text-center">
          <h1 className="text-3xl font-semibold">404 - Not Found</h1>
          <p className="text-muted-foreground mt-2">The requested page does not exist.</p>
        </div>
      </div>
    ),
    children: [
      {
        index: true,
        element: <Navigate to="/dashboard" replace />,
      },
      {
        path: 'dashboard',
        element: <Dashboard />,
      },
      {
        path: 'documents/upload',
        element: guard('/documents/upload', <Upload />),
      },
      {
        path: 'documents',
        element: <Library />,
      },
      {
        path: 'documents/:id',
        element: <DocumentDetails />,
      },
      {
        path: 'review',
        element: guard('/review', <ReviewQueue />),
      },
      {
        path: 'analytics',
        element: guard('/analytics', <Analytics />),
      },
      {
        path: 'audit',
        element: guard('/audit', <AuditLogs />),
      },
      {
        path: 'system-health',
        element: <SystemHealth />,
      },
      {
        path: 'users',
        element: guard('/users', <UserManagement />),
      },
      {
        path: 'settings',
        element: <Settings />,
      },
    ],
  },
]);
