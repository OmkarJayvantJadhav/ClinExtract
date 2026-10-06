import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { Search, Eye, Trash2, Loader2, ChevronLeft, ChevronRight } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { DocumentStatusBadge, ConfidenceIndicator } from '@/components/common/StatusPrimitives';
import { EmptyState, ErrorState } from '@/components/common/FeedbackStates';
import { DeleteDocumentDialog } from '@/features/documents/DeleteDocumentDialog';
import { fetchApi } from '@/services/apiClient';
import { buildDocumentQuery } from '@/lib/documentQuery';
import { useAuth } from '@/context/AuthContext';

const STATUSES = [
  ['REVIEW_REQUIRED', 'Review Required'],
  ['REVIEW_IN_PROGRESS', 'Review In Progress'],
  ['AUTO_ACCEPTED', 'Auto Accepted'],
  ['HUMAN_APPROVED', 'Human Approved'],
  ['HUMAN_REJECTED', 'Human Rejected'],
  ['PROCESSING', 'Processing'],
  ['UPLOADED', 'Queued'],
  ['FAILED', 'Failed'],
];

function useDebounced(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

export function Library() {
  const { hasRole } = useAuth();
  const isAdmin = hasRole('ADMIN');
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [page, setPage] = useState(1);
  const [toDelete, setToDelete] = useState(null);
  const q = useDebounced(searchTerm);

  const filters = { q, status: statusFilter, from, to };
  const filterKey = JSON.stringify(filters);
  const [lastFilterKey, setLastFilterKey] = useState(filterKey);
  if (filterKey !== lastFilterKey) {
    // Any filter change returns to the first page
    setLastFilterKey(filterKey);
    setPage(1);
  }

  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ['documents', { ...filters, page }],
    queryFn: () => fetchApi(buildDocumentQuery({ ...filters, page })),
    placeholderData: keepPreviousData,
    refetchInterval: 10000,
  });

  const docs = data?.items || [];
  const pages = data?.pages || 1;

  return (
    <div className="flex flex-col gap-6 w-full h-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Document Library</h1>
          <p className="text-muted-foreground">Search and track all clinical documents.</p>
        </div>
        {hasRole(['ADMIN', 'OPERATOR']) && (
          <Button asChild>
            <Link to="/documents/upload">Upload Document</Link>
          </Button>
        )}
      </div>

      <Card className="flex-1 flex flex-col">
        <div className="p-4 border-b flex flex-wrap gap-3 items-end justify-between">
          <div className="relative flex-1 min-w-[220px] max-w-md">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              type="search"
              aria-label="Search documents"
              placeholder="Search filename, patient name or ID..."
              className="pl-8"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <div className="flex flex-wrap gap-2 items-end">
            <label className="grid gap-1 text-xs text-muted-foreground">
              Uploaded from
              <Input type="date" value={from} max={to || undefined} onChange={e => setFrom(e.target.value)} className="w-[150px]" />
            </label>
            <label className="grid gap-1 text-xs text-muted-foreground">
              to
              <Input type="date" value={to} min={from || undefined} onChange={e => setTo(e.target.value)} className="w-[150px]" />
            </label>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[190px]" aria-label="Filter by status">
                <SelectValue placeholder="Filter by Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">All Statuses</SelectItem>
                {STATUSES.map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}
              </SelectContent>
            </Select>
            {(searchTerm || statusFilter !== 'ALL' || from || to) && (
              <Button variant="ghost" onClick={() => { setSearchTerm(''); setStatusFilter('ALL'); setFrom(''); setTo(''); }}>Clear</Button>
            )}
          </div>
        </div>

        <CardContent className="p-0 flex-1 overflow-auto">
          {isLoading ? (
            <div className="flex h-40 items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>
          ) : error ? (
            <ErrorState message={error.message} onRetry={refetch} />
          ) : docs.length === 0 ? (
            <div className="py-20">
              <EmptyState title="No documents found" message="Try adjusting your search or filters." />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Document</TableHead>
                  <TableHead>Patient</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Uploaded</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {docs.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell className="font-medium">
                      <Link to={`/documents/${doc.id}`} className="text-primary hover:underline">{doc.filename}</Link>
                      <div className="text-[10px] text-muted-foreground font-mono">{doc.id}</div>
                    </TableCell>
                    <TableCell>
                      <div className="font-medium text-sm">{doc.patient_id || '-'}</div>
                      <div className="text-xs text-muted-foreground">{doc.patient_name}</div>
                    </TableCell>
                    <TableCell><DocumentStatusBadge status={doc.status} /></TableCell>
                    <TableCell>
                      {doc.overall_confidence !== null && doc.overall_confidence !== undefined ? <ConfidenceIndicator score={doc.overall_confidence} /> : <span className="text-muted-foreground text-sm">-</span>}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-right whitespace-nowrap">
                      <Button variant="ghost" size="icon" asChild aria-label="View document">
                        <Link to={`/documents/${doc.id}`}><Eye className="h-4 w-4" /></Link>
                      </Button>
                      {isAdmin && (
                        <Button variant="ghost" size="icon" aria-label="Delete document" className="text-destructive hover:bg-destructive/10"
                          disabled={doc.status === 'PROCESSING'} onClick={() => setToDelete(doc)}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>

        <div className="flex items-center justify-between border-t px-4 py-2 text-sm text-muted-foreground">
          <span>
            {data ? `${data.total} document${data.total === 1 ? '' : 's'}` : ''}
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

      <DeleteDocumentDialog
        key={toDelete?.id || 'none'}
        document={toDelete}
        open={Boolean(toDelete)}
        onOpenChange={(open) => { if (!open) setToDelete(null); }}
      />
    </div>
  );
}
