import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { DocumentStatusBadge } from '@/components/common/StatusPrimitives';
import { EmptyState, ErrorState } from '@/components/common/FeedbackStates';
import { Edit, Clock, PlayCircle, Loader2 } from 'lucide-react';

import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '@/services/apiClient';

function formatAge(iso) {
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} hr${hours === 1 ? '' : 's'}`;
  return `${Math.round(hours / 24)} days`;
}

function useDocumentsByStatus(status) {
  return useQuery({
    queryKey: ['documents', { status }],
    queryFn: () => fetchApi(`/documents?status=${status}&size=100`),
    refetchInterval: 10000
  });
}

export function ReviewQueue() {
  const navigate = useNavigate();
  const [tab, setTab] = useState('pending');

  const pending = useDocumentsByStatus('REVIEW_REQUIRED');
  const inProgress = useDocumentsByStatus('REVIEW_IN_PROGRESS');

  if (pending.isLoading || inProgress.isLoading) {
    return <div className="flex h-[50vh] items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>;
  }

  if (pending.error || inProgress.error) {
    return <ErrorState message={(pending.error || inProgress.error).message} onRetry={() => { pending.refetch(); inProgress.refetch(); }} />;
  }

  // Oldest first: documents waiting longest are reviewed first
  const byAge = (a, b) => new Date(a.created_at) - new Date(b.created_at);
  const pendingDocs = [...(pending.data?.items || [])].sort(byAge);
  const inProgressDocs = [...(inProgress.data?.items || [])].sort(byAge);
  const docsToDisplay = tab === 'in-progress' ? inProgressDocs : pendingDocs;
  const oldest = pendingDocs[0];

  return (
    <div className="flex flex-col gap-6 w-full h-full">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Review Queue</h1>
        <p className="text-muted-foreground">Documents requiring human validation, oldest first.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="bg-primary/5 border-primary/20">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-primary">Awaiting Review</p>
              <h3 className="text-2xl font-bold">{pending.data?.total ?? 0}</h3>
            </div>
            <div className="h-10 w-10 bg-primary/10 rounded-full flex items-center justify-center">
              <Clock className="h-5 w-5 text-primary" />
            </div>
          </CardContent>
        </Card>
        <Card className="bg-warning/10 border-warning/20">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-warning-foreground">In Progress</p>
              <h3 className="text-2xl font-bold">{inProgress.data?.total ?? 0}</h3>
            </div>
            <div className="h-10 w-10 bg-warning/20 rounded-full flex items-center justify-center">
              <PlayCircle className="h-5 w-5 text-warning-foreground" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Oldest Waiting</p>
              <h3 className="text-2xl font-bold">{oldest ? formatAge(oldest.created_at) : '—'}</h3>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="flex-1 flex flex-col">
        <Tabs value={tab} onValueChange={setTab} className="flex-1 flex flex-col">
          <div className="p-4 border-b">
            <TabsList>
              <TabsTrigger value="pending">Awaiting Review ({pendingDocs.length})</TabsTrigger>
              <TabsTrigger value="in-progress">In Progress ({inProgressDocs.length})</TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value={tab} className="flex-1 p-0 m-0 overflow-auto">
            {docsToDisplay.length === 0 ? (
              <div className="py-20">
                <EmptyState title="Queue Empty" message="No documents match this filter." />
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Document</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Waiting</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {docsToDisplay.map((doc) => (
                    <TableRow key={doc.id}>
                      <TableCell>
                        <div className="font-medium">{doc.filename}</div>
                        <div className="text-xs text-muted-foreground font-mono">{doc.id}</div>
                      </TableCell>
                      <TableCell><DocumentStatusBadge status={doc.status} /></TableCell>
                      <TableCell className="text-muted-foreground text-sm">{formatAge(doc.created_at)}</TableCell>
                      <TableCell className="text-right">
                        <Button size="sm" onClick={() => navigate(`/review/workspace/${doc.id}`)}>
                          <Edit className="h-4 w-4 mr-2" /> {doc.status === 'REVIEW_IN_PROGRESS' ? 'Open' : 'Start Review'}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </TabsContent>
        </Tabs>
      </Card>
    </div>
  );
}
