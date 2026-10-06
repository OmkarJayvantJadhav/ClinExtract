import React, { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchApi, getDocumentAudit, apiUrl } from '@/services/apiClient';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { DocumentStatusBadge, ConfidenceIndicator } from '@/components/common/StatusPrimitives';
import { EmptyState } from '@/components/common/FeedbackStates';
import { ArrowLeft, Edit, Clock, Download, Loader2, User, Trash2 } from 'lucide-react';
import { DeleteDocumentDialog } from '@/features/documents/DeleteDocumentDialog';
import { useAuth } from '@/context/AuthContext';
import { ProcessingStatus } from './ProcessingStatus';

export function DocumentDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { hasRole } = useAuth();
  const [deleteOpen, setDeleteOpen] = useState(false);

  // Real API Fetch with Polling
  const { data: doc, isLoading, error } = useQuery({
    queryKey: ['document', id],
    queryFn: () => fetchApi(`/documents/${id}`),
    // Poll every 3 seconds while document is processing/queued.
    // TanStack Query v5 passes the query (not the data) to refetchInterval.
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'UPLOADED' || status === 'PROCESSING' ? 3000 : false;
    }
  });

  const { data: auditData, isLoading: auditLoading } = useQuery({
    queryKey: ['audit-logs', { document_id: id, status: doc?.status }],
    queryFn: () => getDocumentAudit(id)
  });

  let extraction = doc?.extractions && doc.extractions.length > 0 ? doc.extractions[0] : null;
  if (extraction && extraction.extracted_fields) {
    const patientFields = ['patient_name', 'date_of_birth', 'patient_id'];
    const specimenFields = ['specimen_type', 'collection_date', 'received_date'];

    extraction = {
      ...extraction,
      patientInfo: extraction.extracted_fields
        .filter(f => patientFields.includes(f.field_name) || specimenFields.includes(f.field_name))
        .map(f => ({ id: f.id, name: f.field_name.replace(/_/g, ' '), value: f.current_value, corrected: f.is_corrected, state: f.validation_state })),
      laboratoryResults: extraction.extracted_fields
        .filter(f => !patientFields.includes(f.field_name) && !specimenFields.includes(f.field_name))
        .map(f => ({ id: f.id, name: f.field_name.replace(/_/g, ' '), value: f.current_value, unit: f.unit || '', corrected: f.is_corrected, state: f.validation_state }))
    };
  }


  if (isLoading) {
    return <div className="flex h-[50vh] items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>;
  }

  const fieldValue = (name) => doc?.extractions?.[0]?.extracted_fields?.find(f => f.field_name === name)?.current_value;
  const patientName = fieldValue('patient_name');
  const patientId = fieldValue('patient_id');

  if (error || !doc) {
    return <EmptyState title="Document Not Found" message={`Could not locate document ID ${id}`} />;
  }

  return (
    <div className="flex flex-col gap-6 max-w-5xl mx-auto w-full">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link to="/documents"><ArrowLeft className="h-4 w-4" /></Link>
        </Button>
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">{doc.filename}</h1>
          <p className="text-muted-foreground font-mono text-xs">{doc.id}</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <a href={apiUrl(`/documents/${doc.id}/file`)} target="_blank" rel="noopener noreferrer">
              <Download className="h-4 w-4 mr-2" /> Original File
            </a>
          </Button>
          {hasRole('ADMIN') && (
            <Button variant="outline" size="sm" className="text-destructive border-destructive/30 hover:bg-destructive/10"
              disabled={doc.status === 'PROCESSING'} onClick={() => setDeleteOpen(true)}>
              <Trash2 className="h-4 w-4 mr-2" /> Delete
            </Button>
          )}
          {(doc.status === 'REVIEW_REQUIRED' || doc.status === 'REVIEW_IN_PROGRESS') && (
            <Button size="sm" asChild>
              <Link to={`/review/workspace/${doc.id}`}>
                <Edit className="h-4 w-4 mr-2" /> {doc.status === 'REVIEW_IN_PROGRESS' ? 'Open Review' : 'Start Review'}
              </Link>
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

        {/* Left Column - Metadata */}
        <div className="md:col-span-1 space-y-6">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">Overview</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Status</p>
                <div className="mt-1"><DocumentStatusBadge status={doc.status} /></div>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Confidence</p>
                <div className="mt-1">
                  {extraction?.overall_confidence !== null && extraction?.overall_confidence !== undefined
                    ? <ConfidenceIndicator score={extraction.overall_confidence} className="w-full max-w-[200px]" />
                    : 'N/A'}
                </div>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Patient</p>
                <p className="font-medium">{patientName || '—'}{patientId ? ` (${patientId})` : ''}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Uploaded</p>
                <p className="text-sm flex items-center gap-1">
                  <Clock className="h-3 w-3" /> {new Date(doc.created_at).toLocaleString()}
                </p>
              </div>
            </CardContent>
          </Card>

          <ProcessingStatus currentStatus={doc.status} />
        </div>

        {/* Right Column - Extractions & History */}
        <div className="md:col-span-2 space-y-6">

          <Card>
            <CardHeader>
              <CardTitle>Extraction Summary</CardTitle>
              <CardDescription>AI extracted fields from the document</CardDescription>
            </CardHeader>
            <CardContent>
              {!extraction ? (
                <div className="text-center py-6 text-muted-foreground text-sm">Extraction data not available or still processing.</div>
              ) : (
                <div className="space-y-6">
                  {extraction.patientInfo?.length > 0 && (
                    <div>
                      <h4 className="font-medium text-sm border-b pb-1 mb-3">Patient Information</h4>
                      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                        {extraction.patientInfo.map(field => (
                          <div key={field.id} className="flex justify-between p-2 rounded bg-muted/30">
                            <dt className="text-muted-foreground">{field.name}</dt>
                            <dd className="font-medium">{field.value ?? '—'}{field.corrected && <span className="ml-1 text-[10px] text-primary">(corrected)</span>}</dd>
                          </div>
                        ))}
                      </dl>
                    </div>
                  )}
                  {extraction.laboratoryResults?.length > 0 && (
                    <div>
                      <h4 className="font-medium text-sm border-b pb-1 mb-3">Laboratory Results</h4>
                      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                        {extraction.laboratoryResults.map(field => (
                          <div key={field.id} className="flex justify-between p-2 rounded bg-muted/30">
                            <dt className="text-muted-foreground">{field.name}</dt>
                            <dd className="font-medium">{field.value ?? '—'} {field.unit}{field.corrected && <span className="ml-1 text-[10px] text-primary">(corrected)</span>}</dd>
                          </div>
                        ))}
                      </dl>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

            <Card>
              <CardHeader>
                <CardTitle>Review & Audit History</CardTitle>
              </CardHeader>
              <CardContent>
                {auditLoading ? (
                  <div className="flex h-24 items-center justify-center">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                  </div>
                ) : auditData?.items?.length > 0 ? (
                  <div className="space-y-4">
                    {auditData.items.map((entry) => (
                      <div key={entry.id} className="flex gap-4 border-b pb-4 last:border-0 last:pb-0">
                        <div className="mt-1 bg-muted p-2 rounded-full h-8 w-8 flex items-center justify-center shrink-0">
                          <User className="h-4 w-4 text-muted-foreground" />
                        </div>
                        <div>
                          <p className="text-sm">
                            <span className="font-semibold">{entry.user_id || 'System'}</span>
                            <span className="text-muted-foreground mx-1">performed</span>
                            <span className="font-semibold text-primary">{entry.action}</span>
                          </p>
                          {entry.changes && Object.keys(entry.changes).length > 0 && (
                            <div className="text-xs text-muted-foreground mt-1 bg-muted/30 p-2 rounded whitespace-pre-wrap font-mono">
                              {JSON.stringify(entry.changes, null, 2)}
                            </div>
                          )}
                          <p className="text-xs text-muted-foreground mt-1">
                            {new Date(entry.created_at).toLocaleString()}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No audit history found for this document.</p>
                )}
              </CardContent>
            </Card>

        </div>
      </div>
      <DeleteDocumentDialog
        key={deleteOpen ? 'open' : 'closed'}
        document={doc}
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        onDeleted={() => navigate('/documents')}
      />
    </div>
  );
}
