import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { FileText, AlertTriangle, CheckCircle2, XCircle, Activity, Edit3, Loader2 } from 'lucide-react';
import { DocumentStatusBadge } from '@/components/common/StatusPrimitives';
import { Button } from '@/components/ui/button';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getAnalytics, getDetailedHealth, fetchApi } from '@/services/apiClient';
import { useAuth } from '@/context/AuthContext';

export function Dashboard() {
  const { user } = useAuth();

  const { data: analytics, isLoading: analyticsLoading } = useQuery({
    queryKey: ['analytics'],
    queryFn: getAnalytics,
    enabled: user?.role === 'ADMIN',
    refetchInterval: 30000
  });

  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['health-detailed'],
    queryFn: getDetailedHealth,
    refetchInterval: 30000
  });

  const { data: documentsData, isLoading: docsLoading } = useQuery({
    queryKey: ['documents', { page: 1, limit: 5 }],
    queryFn: () => fetchApi('/documents?page=1&size=5'),
    refetchInterval: 30000
  });

  if (analyticsLoading || healthLoading || docsLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center p-8">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const recentDocs = documentsData?.items || [];

  // Default values if user has no access to analytics (e.g. CLINICIAN)
  const defaultAnalytics = {
    documents: { total: 0, processed_today: 0 },
    review: { correction_rate: 0, human_approved: 0, human_rejected: 0 },
    validation: { review_required: 0, auto_accepted: 0 },
    processing: { retrying: 0, failed: 0, succeeded: 0 },
    extraction: { fallback_count: 0 }
  };

  const stats = analytics || defaultAnalytics;

  return (
    <div className="flex flex-col gap-6 w-full">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">Clinical document processing overview</p>
      </div>

      {/* KPI Cards (operational metrics are admin-only) */}
      {!analytics && (
        <Card>
          <CardContent className="p-4 text-sm text-muted-foreground">
            Operational metrics are available to administrators.
          </CardContent>
        </Card>
      )}
      {analytics && <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Total Processed</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.documents.total}</div>
            <p className="text-xs text-muted-foreground">+{stats.documents.uploaded_today ?? stats.documents.processed_today} uploaded today</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Human Correction</CardTitle>
            <Edit3 className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{(stats.review.correction_rate * 100).toFixed(1)}%</div>
            <p className="text-xs text-muted-foreground">Fields modified by users</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Review Required</CardTitle>
            <AlertTriangle className="h-4 w-4 text-warning" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.validation.review_required}</div>
            <p className="text-xs text-muted-foreground">Documents pending review</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Auto Accepted</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-success" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.validation.auto_accepted}</div>
            <p className="text-xs text-muted-foreground">Skipped human review</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Extraction Fallback</CardTitle>
            <XCircle className="h-4 w-4 text-destructive" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.extraction.fallback_count}</div>
            <p className="text-xs text-muted-foreground">AI fallback events</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Failures</CardTitle>
            <Activity className="h-4 w-4 text-destructive" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.processing.failed}</div>
            <p className="text-xs text-muted-foreground">Processing errors</p>
          </CardContent>
        </Card>
      </div>}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        <Card className="col-span-4">
          <CardHeader>
            <CardTitle>System Health Details</CardTitle>
          </CardHeader>
          <CardContent>
            {health && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-lg">Overall Status</span>
                  <span className={`font-bold ${health.status === 'healthy' ? 'text-success' : 'text-destructive'}`}>
                    {health.status.toUpperCase()}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  {Object.entries(health.dependencies || {}).map(([key, value]) => (
                    <div key={key} className="flex justify-between items-center p-2 border rounded">
                      <span className="capitalize">{key}</span>
                      <span className={`text-sm ${value === 'healthy' ? 'text-success' : 'text-destructive'}`}>
                        {value}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {!health && <p className="text-muted-foreground">Unable to fetch system health.</p>}
          </CardContent>
        </Card>
      </div>

      {/* Recent Documents Table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Recent Documents</CardTitle>
          <Button variant="outline" size="sm" asChild>
            <Link to="/documents">View All</Link>
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Document</TableHead>
                <TableHead>Patient ID</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Time</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {recentDocs.length > 0 ? recentDocs.map((doc) => (
                <TableRow key={doc.id}>
                  <TableCell className="font-medium">
                    <Link to={`/documents/${doc.id}`} className="text-primary hover:underline">{doc.filename}</Link>
                  </TableCell>
                  <TableCell className="font-mono text-sm">{doc.patient_id || '-'}</TableCell>
                  <TableCell>{doc.overall_confidence !== null && doc.overall_confidence !== undefined ? `${doc.overall_confidence}%` : '-'}</TableCell>
                  <TableCell><DocumentStatusBadge status={doc.status} /></TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {new Date(doc.created_at).toLocaleString()}
                  </TableCell>
                </TableRow>
              )) : (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-4">No recent documents</TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
