import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, CheckCircle, XCircle, AlertTriangle, Loader2, LogOut } from 'lucide-react';
import { fetchApi, BLOCKING_STATES } from '@/services/apiClient';
import { Button } from '@/components/ui/button';
import { DocumentViewer } from '@/features/review/DocumentViewer';
import { ExtractionPanel } from '@/features/review/ExtractionPanel';
import { DecisionDialogs } from '@/features/review/DecisionDialogs';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { useAuth } from '@/context/AuthContext';

const PATIENT_FIELDS = ['patient_name', 'date_of_birth', 'patient_id'];
const SPECIMEN_FIELDS = ['specimen_type', 'collection_date', 'received_date'];
const CLAIMABLE_STATUSES = ['REVIEW_REQUIRED', 'REVIEW_IN_PROGRESS'];

function toPanelField(f) {
  return {
    id: f.id,
    name: f.field_name.replace(/_/g, ' '),
    value: f.current_value,
    original_value: f.original_value,
    unit: f.unit || '',
    referenceRange: f.reference_range,
    abnormalFlag: f.abnormal_flag,
    state: f.validation_state,
    validationMessage: (f.validation_messages || []).join('; '),
    confidence: f.confidence,
    page_num: f.page_num,
    bbox: f.bbox_normalized,
  };
}

// Keeps the review claim alive while the workspace is open (claims expire after inactivity)
const HEARTBEAT_MS = 5 * 60 * 1000;

const SHORTCUTS = 'j/k next/previous field · n next issue · e edit · a approve · r reject';

async function nextReviewPath(currentId) {
  try {
    const data = await fetchApi('/documents?status=REVIEW_REQUIRED&sort=priority&size=2');
    const next = data.items.find(d => d.id !== currentId);
    return next ? `/review/workspace/${next.id}` : '/review';
  } catch {
    return '/review';
  }
}

function formatErrorDetail(error) {
  const detail = error?.detail;
  if (detail?.fields?.length) {
    return `${detail.message} ${detail.fields.map(f => `${f.field_name.replace(/_/g, ' ')} (${f.state.toLowerCase()})`).join(', ')}`;
  }
  return error?.message || 'Request failed';
}

export function Workspace() {
  const { id } = useParams();
  // A fresh workspace per document (its own claim, corrections and selection), also when
  // moving straight to the next document after a decision.
  return <ReviewWorkspace key={id} id={id} />;
}

function ReviewWorkspace({ id }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { hasRole } = useAuth();
  const canReview = hasRole(['ADMIN', 'REVIEWER']);

  const { data: doc, isLoading, error } = useQuery({
    queryKey: ['document', id],
    queryFn: () => fetchApi(`/documents/${id}`),
  });

  // Claim the review once the document is loaded. The backend returns the existing review
  // when this reviewer already holds the claim (e.g. after a page reload).
  const claimMutation = useMutation({
    mutationFn: () => fetchApi(`/reviews/${id}/claim`, { method: 'POST' }),
  });

  const { mutate: claim, isIdle: claimIdle } = claimMutation;
  useEffect(() => {
    if (canReview && doc && CLAIMABLE_STATUSES.includes(doc.status) && claimIdle) {
      claim();
    }
  }, [canReview, doc, claimIdle, claim]);

  const invalidateDocument = () => {
    queryClient.invalidateQueries({ queryKey: ['document', id] });
    queryClient.invalidateQueries({ queryKey: ['documents'] });
    queryClient.invalidateQueries({ queryKey: ['audit-logs'] });
  };

  const completeMutation = useMutation({
    mutationFn: (data) => fetchApi(`/reviews/${id}/complete`, {
      method: 'POST',
      body: JSON.stringify(data)
    }),
    onSuccess: async () => {
      invalidateDocument();
      // Straight on to the next document waiting for review
      navigate(await nextReviewPath(id));
    },
  });

  const releaseMutation = useMutation({
    mutationFn: () => fetchApi(`/reviews/${id}/release`, { method: 'POST' }),
    onSuccess: () => {
      invalidateDocument();
      navigate('/review');
    },
  });

  const extraction = useMemo(() => {
    const ext = doc?.extractions?.[0];
    if (!ext) return null;
    const fields = ext.extracted_fields || [];
    return {
      ...ext,
      patientInfo: fields
        .filter(f => PATIENT_FIELDS.includes(f.field_name) || SPECIMEN_FIELDS.includes(f.field_name))
        .map(toPanelField),
      laboratoryResults: fields
        .filter(f => !PATIENT_FIELDS.includes(f.field_name) && !SPECIMEN_FIELDS.includes(f.field_name))
        .map(toPanelField),
    };
  }, [doc]);

  const allFields = useMemo(
    () => extraction ? [...extraction.patientInfo, ...extraction.laboratoryResults] : [],
    [extraction]
  );

  const [activeFieldId, setActiveFieldId] = useState(null);
  const [editingFieldId, setEditingFieldId] = useState(null);
  const [corrections, setCorrections] = useState({});
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogType, setDialogType] = useState('APPROVE');

  // Until the reviewer picks a field, select the first field with an issue (or the first field)
  const defaultFieldId = useMemo(() => {
    const first = allFields.find(f => f.state !== 'VALID' && f.bbox) || allFields.find(f => f.bbox) || allFields[0];
    return first?.id ?? null;
  }, [allFields]);
  const selectedId = activeFieldId ?? defaultFieldId;
  const selected = allFields.find(f => f.id === selectedId);
  const selectedField = selected ? { page_num: selected.page_num, bbox: selected.bbox } : null;

  const reviewId = claimMutation.data?.id;
  const isReadOnly = !canReview || (!CLAIMABLE_STATUSES.includes(doc?.status) && !reviewId);

  // Only unusable values block approval; abnormal results (e.g. outside reference range)
  // are confirmed explicitly in the approval dialog.
  const unresolvedIssues = allFields.filter(f => BLOCKING_STATES.includes(f.state) && corrections[f.id] === undefined);
  const hasUnresolvedIssues = unresolvedIssues.length > 0;
  const canReject = !isReadOnly && Boolean(reviewId) && !completeMutation.isPending;
  const canApprove = canReject && !hasUnresolvedIssues;

  const handleDecision = (type) => {
    completeMutation.reset();
    setDialogType(type);
    setDialogOpen(true);
  };

  useEffect(() => {
    if (!reviewId) return undefined;
    const timer = setInterval(() => {
      fetchApi(`/reviews/${id}/heartbeat`, { method: 'POST' }).catch(() => {});
    }, HEARTBEAT_MS);
    return () => clearInterval(timer);
  }, [reviewId, id]);

  // Keyboard shortcuts (ignored while typing, editing a field or in a dialog)
  useEffect(() => {
    const onKeyDown = (e) => {
      if (dialogOpen || editingFieldId || e.metaKey || e.ctrlKey || e.altKey) return;
      const target = e.target;
      if (target?.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON'].includes(target?.tagName)) return;
      const index = allFields.findIndex(f => f.id === selectedId);
      const select = (field) => {
        if (!field) return;
        e.preventDefault();
        setActiveFieldId(field.id);
      };
      if (e.key === 'j' || e.key === 'ArrowDown') select(allFields[Math.min(index + 1, allFields.length - 1)]);
      else if (e.key === 'k' || e.key === 'ArrowUp') select(allFields[Math.max(index - 1, 0)]);
      else if (e.key === 'n') {
        const ahead = [...allFields.slice(index + 1), ...allFields.slice(0, index + 1)];
        select(ahead.find(f => f.state && f.state !== 'VALID' && corrections[f.id] === undefined));
      } else if ((e.key === 'e' || e.key === 'Enter') && !isReadOnly && selectedId) {
        e.preventDefault();
        setEditingFieldId(selectedId);
      } else if (e.key === 'a' && canApprove) {
        e.preventDefault();
        handleDecision('APPROVE');
      } else if (e.key === 'r' && canReject) {
        e.preventDefault();
        handleDecision('REJECT');
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  });

  if (isLoading) {
    return <div className="flex h-[50vh] items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>;
  }

  if (claimMutation.isError) {
    const conflict = claimMutation.error?.status === 409;
    return (
      <div className="p-8 space-y-4">
        <div className="text-destructive font-medium text-lg">
          {conflict && claimMutation.error.message === 'DOCUMENT_ALREADY_CLAIMED'
            ? 'This document is currently being reviewed by another reviewer.'
            : `Unable to start the review: ${claimMutation.error?.message}`}
        </div>
        <Button variant="outline" asChild><Link to="/review">Back to review queue</Link></Button>
      </div>
    );
  }

  if (!doc || !extraction) {
    return (
      <div className="p-8 text-destructive">
        Document workspace data not found.
        {error && <div className="mt-4 font-mono text-xs">{String(error.message)}</div>}
      </div>
    );
  }

  const warnings = allFields
    .filter(f => f.state && f.state !== 'VALID' && !BLOCKING_STATES.includes(f.state) && corrections[f.id] === undefined)
    .map(f => ({ id: f.id, name: f.name, value: `${f.value ?? ''} ${f.unit}`.trim(), state: f.state }));
  const correctedFields = allFields
    .filter(f => corrections[f.id] !== undefined)
    .map(f => ({ id: f.id, name: f.name, original: f.value, newValue: corrections[f.id] }));

  const handleFieldSelect = (field) => {
    setActiveFieldId(field.id);
  };

  const handleFieldEdit = (fieldId, newValue) => {
    setCorrections(prev => {
      const next = { ...prev };
      if (newValue === undefined) {
        delete next[fieldId];
      } else {
        next[fieldId] = newValue;
      }
      return next;
    });
  };

  const submitDecision = ({ reasons, rejectionReason }) => {
    if (!reviewId) return;

    if (dialogType === 'REJECT') {
      completeMutation.mutate({
        review_id: reviewId,
        decision: 'HUMAN_REJECTED',
        corrections: [],
        rejection_reason: rejectionReason,
      });
    } else {
      completeMutation.mutate({
        review_id: reviewId,
        decision: 'HUMAN_APPROVED',
        corrections: correctedFields.map(f => ({
          extracted_field_id: f.id,
          new_value: f.newValue === '' ? null : f.newValue,
          reason: (reasons?.[f.id] || '').trim(),
        })),
        rejection_reason: null,
      });
    }
    setDialogOpen(false);
  };

  const confidence = extraction.overall_confidence;

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] w-full overflow-hidden bg-background">
      {/* Top Bar */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-card shrink-0">
        <div className="flex items-center gap-4 min-w-0">
          <Button variant="ghost" size="icon" asChild>
            <Link to="/review"><ArrowLeft className="h-4 w-4" /></Link>
          </Button>
          <div className="min-w-0">
            <h2 className="text-lg font-semibold tracking-tight truncate" title={doc.filename}>{doc.filename}</h2>
            <p className="text-xs text-muted-foreground font-mono truncate">{doc.id} · {doc.status.replace(/_/g, ' ')}</p>
            {!isReadOnly && <p className="text-[10px] text-muted-foreground truncate" title="Keyboard shortcuts">{SHORTCUTS}</p>}
          </div>

          <div className="ml-6 pl-6 border-l flex items-center gap-6">
             <div className="flex flex-col max-w-[150px]">
                <span className="text-[10px] uppercase text-muted-foreground font-bold tracking-wider truncate">
                  Extractor: {extraction.extractor_type || 'rule_based'}
                </span>
                <span className="font-mono text-[10px] text-muted-foreground truncate" title={`${extraction.provider} / ${extraction.model_version || 'N/A'}`}>
                  {extraction.provider} / {extraction.model_version || 'N/A'}
                </span>
             </div>
             <div className="flex flex-col">
                <span className="text-[10px] uppercase text-muted-foreground font-bold tracking-wider">Confidence</span>
                <span className="font-mono text-sm font-medium">{confidence !== null && confidence !== undefined ? `${confidence}%` : '—'}</span>
             </div>
             <div className="flex flex-col">
                <span className="text-[10px] uppercase text-muted-foreground font-bold tracking-wider">Human Corrections</span>
                <span className="font-mono text-sm font-medium">{correctedFields.length}</span>
             </div>
             <div className="flex flex-col">
                <span className="text-[10px] uppercase text-muted-foreground font-bold tracking-wider">Must Fix</span>
                <span className={`font-mono text-sm font-medium ${hasUnresolvedIssues ? 'text-destructive' : 'text-success'}`}>
                  {unresolvedIssues.length}
                </span>
             </div>
          </div>
        </div>

        {!isReadOnly && (
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => releaseMutation.mutate()} disabled={!reviewId || releaseMutation.isPending}>
              <LogOut className="h-4 w-4 mr-2" /> Release
            </Button>
            <Button variant="outline" className="text-destructive hover:bg-destructive/10 border-destructive/20" onClick={() => handleDecision('REJECT')} disabled={!canReject}>
              <XCircle className="h-4 w-4 mr-2" /> Reject Document
            </Button>

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span>
                    <Button
                      className="bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
                      onClick={() => handleDecision('APPROVE')}
                      disabled={!canApprove}
                    >
                      {completeMutation.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <CheckCircle className="h-4 w-4 mr-2" />}
                      Approve & Submit
                    </Button>
                  </span>
                </TooltipTrigger>
                {hasUnresolvedIssues && (
                  <TooltipContent className="bg-destructive text-destructive-foreground border-destructive/20 flex items-center">
                    <AlertTriangle className="h-4 w-4 mr-2" />
                    Correct {unresolvedIssues.length} missing or invalid field(s) before approval.
                  </TooltipContent>
                )}
              </Tooltip>
            </TooltipProvider>
          </div>
        )}
      </div>

      {(completeMutation.isError || releaseMutation.isError) && (
        <div className="px-4 py-2 text-sm bg-destructive/10 text-destructive border-b border-destructive/20">
          {formatErrorDetail(completeMutation.error || releaseMutation.error)}
        </div>
      )}
      {isReadOnly && (
        <div className="px-4 py-2 text-sm bg-muted text-muted-foreground border-b">
          Read-only: this document is not awaiting review{canReview ? '' : ' or you do not have reviewer permissions'}.
        </div>
      )}

      {/* Two-Panel Workspace */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: the actual uploaded document */}
        <div className="w-1/2 border-r bg-muted/20 overflow-auto relative p-6 flex justify-center shadow-inner">
          <DocumentViewer documentId={id} activeField={selectedField} />
        </div>

        {/* Right: Extraction Panel */}
        <div className="w-1/2 overflow-auto bg-card border-l border-white shadow-[-4px_0_15px_-3px_rgba(0,0,0,0.05)]">
          <ExtractionPanel
            extraction={extraction}
            corrections={isReadOnly ? {} : corrections}
            activeFieldId={selectedId}
            editingFieldId={isReadOnly ? null : editingFieldId}
            onFieldSelect={handleFieldSelect}
            onEditingChange={(fieldId) => setEditingFieldId(isReadOnly ? null : fieldId)}
            onFieldEdit={isReadOnly ? () => {} : handleFieldEdit}
          />
        </div>
      </div>

      <DecisionDialogs
        key={dialogOpen ? `${dialogType}-open` : 'closed'}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        type={dialogType}
        onSubmit={submitDecision}
        correctedFields={correctedFields}
        warnings={warnings}
        isSubmitting={completeMutation.isPending}
      />
    </div>
  );
}
