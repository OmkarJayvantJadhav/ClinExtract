import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Search, SlidersHorizontal, Eye } from 'lucide-react';
import { DocumentStatusBadge, ConfidenceIndicator } from '@/components/common/StatusPrimitives';
import { EmptyState } from '@/components/common/FeedbackStates';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '@/services/apiClient';
import { Loader2 } from 'lucide-react';

export function Library() {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');

  const { data: documentsData, isLoading } = useQuery({
    queryKey: ['documents', { status: statusFilter !== 'ALL' ? statusFilter : null }],
    queryFn: () => {
      let url = '/documents?size=50';
      if (statusFilter !== 'ALL') url += `&status=${statusFilter}`;
      return fetchApi(url);
    },
    refetchInterval: 10000
  });

  const docs = documentsData?.items || [];

  const filteredDocs = docs.filter(doc => {
    const term = searchTerm.toLowerCase();
    const matchesSearch =
      doc.id.toLowerCase().includes(term) ||
      doc.filename.toLowerCase().includes(term) ||
      (doc.patient_id && doc.patient_id.toLowerCase().includes(term)) ||
      (doc.patient_name && doc.patient_name.toLowerCase().includes(term));

    return matchesSearch;
  });

  if (isLoading) {
    return <div className="flex h-[50vh] items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>;
  }

  return (
    <div className="flex flex-col gap-6 w-full h-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Document Library</h1>
          <p className="text-muted-foreground">Manage and track all clinical documents.</p>
        </div>
        <Button asChild>
          <Link to="/documents/upload">Upload Document</Link>
        </Button>
      </div>

      <Card className="flex-1 flex flex-col">
        <div className="p-4 border-b flex flex-wrap gap-4 items-center justify-between">
          <div className="flex gap-4 flex-1 max-w-md">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                type="search"
                placeholder="Search ID, Patient..."
                className="pl-8"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
          </div>
          <div className="flex gap-2 items-center">
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filter by Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">All Statuses</SelectItem>
                <SelectItem value="REVIEW_REQUIRED">Review Required</SelectItem>
                <SelectItem value="AUTO_ACCEPTED">Auto Accepted</SelectItem>
                <SelectItem value="HUMAN_APPROVED">Human Approved</SelectItem>
                <SelectItem value="PROCESSING">Processing</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" size="icon">
              <SlidersHorizontal className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <CardContent className="p-0 flex-1 overflow-auto">
          {filteredDocs.length === 0 ? (
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
                {filteredDocs.map((doc) => (
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
                    <TableCell className="text-right">
                      <Button variant="ghost" size="icon" asChild>
                        <Link to={`/documents/${doc.id}`}>
                          <Eye className="h-4 w-4" />
                        </Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
