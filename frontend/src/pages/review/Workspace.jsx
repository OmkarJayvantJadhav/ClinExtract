import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { fetchApi } from '@/services/apiClient';
import { Button } from '@/components/ui/button';

const fallbackLayout = {
  header: { text: "CLINICAL LABORATORY REPORT", address: "123 Medical Center Blvd", phone: "(555) 123-4567" },
  patientInfo: [
    { label: "Patient Name:", value: "John Doe", bbox: [5, 20, 20, 2] },
    { label: "DOB:", value: "01/15/1980", bbox: [5, 22, 10, 2] },
    { label: "Patient ID:", value: "PT-88912", bbox: [5, 24, 15, 2] }
  ],
  specimenInfo: [
    { label: "Specimen:", value: "Blood", bbox: [55, 20, 15, 2] },
    { label: "Collected:", value: "2026-08-20 08:30", bbox: [55, 22, 20, 2] }
  ],
  resultsTable: {
    headers: ["Test", "Result", "Units", "Ref Range", "Flag"],
    rows: [
      { test: "Hemoglobin", result: "13.2", units: "g/dL", range: "13.8-17.2", flag: "L", valBbox: [30, 45, 10, 2] },
      { test: "WBC Count", result: "6.5", units: "x10^3/uL", range: "4.5-11.0", flag: "", valBbox: [30, 48, 10, 2] }
    ]
  }
};
import { ArrowLeft, CheckCircle, XCircle, AlertTriangle, Loader2 } from 'lucide-react';
import { SyntheticDocumentViewer } from '@/features/review/SyntheticDocumentViewer';
import { ExtractionPanel } from '@/features/review/ExtractionPanel';
import { DecisionDialogs } from '@/features/review/DecisionDialogs';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

export function Workspace() {
  const { id } = useParams();
  const navigate = useNavigate();

  // Claim the review on mount/load
  const claimMutation = useMutation({
    mutationFn: () => fetchApi(`/api/v1/reviews/${id}/claim`, { method: 'POST' }),
  });

  const { data: doc, isLoading, error } = useQuery({
    queryKey: ['document', id],
    queryFn: () => fetchApi(`/documents/${id}`),
    // Wait until claimed if needed, but the GET works regardless.
  });

  useEffect(() => {
    if (doc && doc.status === 'REVIEW_REQUIRED') {
      claimMutation.mutate();
    }
  }, [doc?.status]);

  const completeMutation = useMutation({
    mutationFn: (data) => fetchApi(`/api/v1/reviews/${id}/complete`, {
      method: 'POST',
      body: JSON.stringify(data)
    }),
    onSuccess: () => navigate('/documents'),
    onError: (err) => console.error("Review complete failed:", err)
  });

  let initialExtraction = null;
  if (doc?.extractions?.length > 0) {
    const ext = doc.extractions[0];
    const patientFields = ['patient_name', 'date_of_birth', 'patient_id'];
    const specimenFields = ['specimen_type', 'collection_date', 'received_date'];
    
    initialExtraction = {
      ...ext,
      patientInfo: ext.extracted_fields
        .filter(f => patientFields.includes(f.field_name) || specimenFields.includes(f.field_name))
        .map(f => ({ 
          id: f.id,
          name: f.field_name.replace(/_/g, ' '), 
          value: f.current_value, 
          original_value: f.original_value,
          state: f.validation_state,
          messages: f.validation_messages,
          bbox: f.bbox_normalized
        })),
      laboratoryResults: ext.extracted_fields
        .filter(f => !patientFields.includes(f.field_name) && !specimenFields.includes(f.field_name))
        .map(f => ({ 
          id: f.id,
          name: f.field_name.replace(/_/g, ' '), 
          value: f.current_value, 
          original_value: f.original_value,
          state: f.validation_state,
          messages: f.validation_messages,
          bbox: f.bbox_normalized,
          unit: '' 
        }))
    };
  }

  const layout = fallbackLayout;

  const [activeBbox, setActiveBbox] = useState(null);
  const [corrections, setCorrections] = useState({});
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogType, setDialogType] = useState('APPROVE');

  // Auto-select first field with an issue, or first field overall
  useEffect(() => {
    if (initialExtraction) {
      const allFields = [
        ...(initialExtraction.patientInfo || []),
        ...(initialExtraction.documentInfo || []),
        ...(initialExtraction.laboratoryResults || [])
      ];
      
      const firstIssue = allFields.find(f => f.state !== 'VALID');
      if (firstIssue && firstIssue.bbox) {
        setActiveBbox(firstIssue.bbox);
      } else if (allFields[0] && allFields[0].bbox) {
        setActiveBbox(allFields[0].bbox);
      }
    }
  }, [initialExtraction]);

  if (isLoading) {
    return <div className="flex h-[50vh] items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>;
  }

  if (claimMutation.isError && claimMutation.error?.status === 409) {
    return <div className="p-8 text-destructive font-medium text-lg">Document is currently being reviewed by another reviewer.</div>;
  }

  if (!doc || !initialExtraction) {
    return (
      <div className="p-8 text-destructive">
        Document workspace data not found. 
        {error && <div className="mt-4 font-mono text-xs">{String(error.message)}</div>}
      </div>
    );
  }

  const allFields = [
    ...(initialExtraction.patientInfo || []),
    ...(initialExtraction.documentInfo || []),
    ...(initialExtraction.laboratoryResults || [])
  ];

  // Calculate unresolved issues: fields that are NOT valid and have NOT been corrected
  const unresolvedIssues = allFields.filter(f => f.state !== 'VALID' && corrections[f.id] === undefined);
  const hasUnresolvedIssues = unresolvedIssues.length > 0;

  const handleFieldSelect = (bbox) => {
    setActiveBbox(bbox);
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

  const handleDecision = (type) => {
    setDialogType(type);
    setDialogOpen(true);
  };

  const submitDecision = (reason) => {
    const reviewId = claimMutation.data?.id;
    if (!reviewId) return;

    const formattedCorrections = Object.entries(corrections).map(([fieldId, newValue]) => ({
      extracted_field_id: fieldId,
      new_value: newValue,
      reason: reason || "Manual correction"
    }));

    completeMutation.mutate({
      review_id: reviewId,
      decision: dialogType === 'APPROVE' ? 'HUMAN_APPROVED' : 'HUMAN_REJECTED',
      corrections: formattedCorrections,
      rejection_reason: dialogType === 'REJECT' ? reason : null
    });
    
    setDialogOpen(false);
  };


  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] w-full overflow-hidden bg-background">
      {/* Top Bar */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-card shrink-0">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link to="/review"><ArrowLeft className="h-4 w-4" /></Link>
          </Button>
          <div>
            <h2 className="text-lg font-semibold tracking-tight">{doc.id}</h2>
            <p className="text-xs text-muted-foreground">{doc.type}</p>
          </div>
          
          <div className="ml-6 pl-6 border-l flex items-center gap-6">
             <div className="flex flex-col max-w-[150px]">
                <span className="text-[10px] uppercase text-muted-foreground font-bold tracking-wider truncate">
                  Extractor: {initialExtraction.extractor_type || 'Rule Based'}
                </span>
                <span className="font-mono text-[10px] text-muted-foreground truncate" title={`${initialExtraction.provider} / ${initialExtraction.model_version || 'N/A'}`}>
                  {initialExtraction.provider} / {initialExtraction.model_version || 'N/A'}
                </span>
             </div>
             <div className="flex flex-col">
                <span className="text-[10px] uppercase text-muted-foreground font-bold tracking-wider">AI Confidence</span>
                <span className="font-mono text-sm font-medium">{doc.confidence}%</span>
             </div>
             <div className="flex flex-col">
                <span className="text-[10px] uppercase text-muted-foreground font-bold tracking-wider">Human Corrections</span>
                <span className="font-mono text-sm font-medium">{Object.keys(corrections).length}</span>
             </div>
             <div className="flex flex-col">
                <span className="text-[10px] uppercase text-muted-foreground font-bold tracking-wider">Unresolved Issues</span>
                <span className={`font-mono text-sm font-medium ${hasUnresolvedIssues ? 'text-destructive' : 'text-success'}`}>
                  {unresolvedIssues.length}
                </span>
             </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" className="text-destructive hover:bg-destructive/10 border-destructive/20" onClick={() => handleDecision('REJECT')}>
            <XCircle className="h-4 w-4 mr-2" /> Reject Document
          </Button>
          
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <span>
                  <Button 
                    className="bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed" 
                    onClick={() => handleDecision('APPROVE')}
                    disabled={hasUnresolvedIssues}
                  >
                    <CheckCircle className="h-4 w-4 mr-2" /> Approve & Submit
                  </Button>
                </span>
              </TooltipTrigger>
              {hasUnresolvedIssues && (
                <TooltipContent className="bg-destructive text-destructive-foreground border-destructive/20 flex items-center">
                  <AlertTriangle className="h-4 w-4 mr-2" />
                  Must resolve {unresolvedIssues.length} validation issue(s) before approval.
                </TooltipContent>
              )}
            </Tooltip>
          </TooltipProvider>
        </div>
      </div>

      {/* Two-Panel Workspace */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Document Viewer */}
        <div className="w-1/2 border-r bg-muted/20 overflow-auto relative p-6 flex justify-center shadow-inner">
          <SyntheticDocumentViewer layout={layout} activeBbox={activeBbox} />
        </div>
        
        {/* Right: Extraction Panel */}
        <div className="w-1/2 overflow-auto bg-card border-l border-white shadow-[-4px_0_15px_-3px_rgba(0,0,0,0.05)]">
          <ExtractionPanel 
            extraction={initialExtraction} 
            corrections={corrections}
            onFieldSelect={handleFieldSelect}
            onFieldEdit={handleFieldEdit}
          />
        </div>
      </div>

      <DecisionDialogs 
        open={dialogOpen} 
        onOpenChange={setDialogOpen} 
        type={dialogType}
        onSubmit={submitDecision}
      />
    </div>
  );
}
