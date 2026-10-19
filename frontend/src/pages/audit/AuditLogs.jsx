import React, { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Search, Loader2, ChevronLeft, ChevronRight } from 'lucide-react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { getAuditLogs } from '@/services/apiClient';
import { Button } from '@/components/ui/button';
import { ErrorState } from '@/components/common/FeedbackStates';

const PAGE_SIZE = 100;

export function AuditLogs() {
  const [searchDocId, setSearchDocId] = useState('');
  const [page, setPage] = useState(1);

  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ['audit-logs', { document_id: searchDocId, page }],
    queryFn: () => getAuditLogs({ ...(searchDocId ? { document_id: searchDocId } : {}), page, size: PAGE_SIZE }),
    placeholderData: keepPreviousData,
    refetchInterval: 60000,
  });

  const logs = data?.items || [];
  const pages = Math.max(1, Math.ceil((data?.total || 0) / PAGE_SIZE));

  return (
    <div className="flex flex-col gap-6 w-full h-full">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Audit Logs</h1>
        <p className="text-muted-foreground">Immutable record of system and user actions.</p>
      </div>

      <Card className="flex-1 flex flex-col">
        <div className="p-4 border-b flex flex-wrap gap-4 items-center">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input 
              type="search" 
              placeholder="Search by Document ID..." 
              className="pl-8" 
              value={searchDocId}
              onChange={(e) => { setSearchDocId(e.target.value); setPage(1); }}
            />
          </div>
        </div>
        
        <CardContent className="p-0 flex-1 overflow-auto">
          {isLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <ErrorState message={error.message} onRetry={refetch} />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Timestamp</TableHead>
                  <TableHead>User ID / Actor</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Document Ref</TableHead>
                  <TableHead>Correlation ID</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.length > 0 ? logs.map((log) => (
                  <TableRow key={log.id} className="hover:bg-muted/50 cursor-pointer">
                    <TableCell className="text-sm font-mono">{new Date(log.created_at).toLocaleString()}</TableCell>
                    <TableCell className="text-sm">{log.user_id || 'System'}</TableCell>
                    <TableCell className="font-medium text-xs tracking-wider">{log.action}</TableCell>
                    <TableCell className="text-sm">{log.document_id}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{log.correlation_id || '-'}</TableCell>
                  </TableRow>
                )) : (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">No logs found</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>

        <div className="flex items-center justify-between border-t px-4 py-2 text-sm text-muted-foreground">
          <span>
            {data ? `${data.total} event${data.total === 1 ? '' : 's'}` : ''}
            {isFetching && !isLoading && <Loader2 className="ml-2 inline h-3 w-3 animate-spin" />}
          </span>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon" aria-label="Previous page" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span>Page {page} of {pages}</span>
            <Button variant="outline" size="icon" aria-label="Next page" disabled={page >= pages} onClick={() => setPage(p => p + 1)}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
