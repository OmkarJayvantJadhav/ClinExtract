import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { CheckCircle2, Circle, Loader2, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

const stages = [
  { id: 'QUEUED', label: 'Queued', description: 'Waiting for available worker' },
  { id: 'PROCESSING', label: 'Processing', description: 'Extracting and analyzing document' },
  { id: 'REVIEW', label: 'Review', description: 'Human validation (if required)' },
  { id: 'COMPLETED', label: 'Completed', description: 'Document finalized' },
];

// Document status -> index of the stage it is currently in
const STATUS_TO_STAGE = {
  UPLOADED: 0,
  PROCESSING: 1,
  REVIEW_REQUIRED: 2,
  REVIEW_IN_PROGRESS: 2,
  AUTO_ACCEPTED: 3,
  HUMAN_APPROVED: 3,
  HUMAN_REJECTED: 3,
};

const FINAL_DESCRIPTIONS = {
  AUTO_ACCEPTED: 'Auto-accepted (passed all validation)',
  HUMAN_APPROVED: 'Approved by a reviewer',
  HUMAN_REJECTED: 'Rejected by a reviewer',
};

export function ProcessingStatus({ currentStatus }) {
  const isFailed = currentStatus === 'FAILED';
  const isFinal = currentStatus in FINAL_DESCRIPTIONS;
  // A failed document stopped during processing
  const activeIndex = isFailed ? 1 : (STATUS_TO_STAGE[currentStatus] ?? 0);

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg">Processing Pipeline</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-6">
          {stages.map((stage, idx) => {
            const isCompleted = idx < activeIndex || (isFinal && idx === activeIndex);
            const isCurrent = idx === activeIndex && !isFinal && !isFailed;
            const isFailedStage = isFailed && idx === activeIndex;
            const isPending = idx > activeIndex;
            const description = idx === 3 && isFinal
              ? FINAL_DESCRIPTIONS[currentStatus]
              : isFailedStage ? 'Processing failed' : stage.description;

            return (
              <div key={stage.id} className={cn("flex gap-4 relative", isPending && "opacity-50")}>
                <div className="flex flex-col items-center">
                  <div className="z-10 bg-card">
                    {isFailedStage ? (
                      <XCircle className="h-5 w-5 text-destructive" />
                    ) : isCompleted ? (
                      <CheckCircle2 className={cn("h-5 w-5", currentStatus === 'HUMAN_REJECTED' && idx === 3 ? "text-destructive" : "text-success")} />
                    ) : isCurrent ? (
                      <Loader2 className="h-5 w-5 text-primary animate-spin" />
                    ) : (
                      <Circle className="h-5 w-5 text-muted-foreground" />
                    )}
                  </div>
                  {idx !== stages.length - 1 && (
                    <div className={cn("w-px h-full absolute top-5 bottom-[-1.5rem]", idx < activeIndex ? "bg-success" : "bg-border")} />
                  )}
                </div>
                <div className="pb-1">
                  <p className={cn("text-sm font-medium", isCurrent && "text-primary", isFailedStage && "text-destructive")}>
                    {stage.label}
                  </p>
                  <p className="text-xs text-muted-foreground">{description}</p>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
