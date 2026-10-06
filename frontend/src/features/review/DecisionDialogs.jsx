import React, { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';

/**
 * type: 'APPROVE' | 'REJECT'
 * correctedFields: [{ id, name, original, newValue }]  - each needs a reason on approval
 * warnings: [{ id, name, value, state }]                - abnormal-but-valid values to acknowledge
 * onSubmit: REJECT  -> ({ rejectionReason })
 *           APPROVE -> ({ reasons: { [fieldId]: string } })
 */
export function DecisionDialogs({ open, onOpenChange, type, onSubmit, correctedFields = [], warnings = [], isSubmitting = false }) {
  const [reason, setReason] = useState('');
  const [comment, setComment] = useState('');
  const [fieldReasons, setFieldReasons] = useState({});
  const [acknowledged, setAcknowledged] = useState(false);
  const isReject = type === 'REJECT';
  // Form state starts fresh each time because the parent re-keys this component when it opens.

  const missingReasons = correctedFields.some(f => !(fieldReasons[f.id] || '').trim());
  const canSubmit = isReject
    ? Boolean(reason)
    : !missingReasons && (warnings.length === 0 || acknowledged);

  const handleSubmit = () => {
    if (isReject) {
      onSubmit({ rejectionReason: comment.trim() ? `${reason}: ${comment.trim()}` : reason });
    } else {
      onSubmit({ reasons: fieldReasons });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isReject ? 'Reject Document' : 'Approve Document'}</DialogTitle>
          <DialogDescription>
            {isReject
              ? 'Please provide a reason for rejecting this document extraction.'
              : 'By approving, you confirm that every field matches the source document.'}
          </DialogDescription>
        </DialogHeader>

        {isReject && (
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>Rejection Reason *</Label>
              <Select value={reason} onValueChange={setReason}>
                <SelectTrigger>
                  <SelectValue placeholder="Select reason" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Poor document quality">Poor document quality</SelectItem>
                  <SelectItem value="Missing information">Missing critical information</SelectItem>
                  <SelectItem value="Incorrect extraction">System failed to extract properly</SelectItem>
                  <SelectItem value="Unsupported document">Unsupported document type</SelectItem>
                  <SelectItem value="Other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>Additional Comments (Optional)</Label>
              <Input value={comment} onChange={e => setComment(e.target.value)} placeholder="Provide context..." />
            </div>
          </div>
        )}

        {!isReject && correctedFields.length > 0 && (
          <div className="grid gap-3 py-2">
            <Label className="text-sm">Reason for each correction *</Label>
            {correctedFields.map(f => (
              <div key={f.id} className="grid gap-1 rounded border p-2">
                <div className="text-xs">
                  <span className="font-semibold uppercase tracking-wide text-muted-foreground">{f.name}</span>
                  <span className="ml-2 font-mono line-through text-muted-foreground">{f.original ?? '(empty)'}</span>
                  <span className="mx-1">→</span>
                  <span className="font-mono font-semibold">{f.newValue || '(empty)'}</span>
                </div>
                <Input
                  value={fieldReasons[f.id] || ''}
                  onChange={e => setFieldReasons(prev => ({ ...prev, [f.id]: e.target.value }))}
                  placeholder="e.g. OCR misread digit; verified against source"
                />
              </div>
            ))}
          </div>
        )}

        {!isReject && warnings.length > 0 && (
          <div className="grid gap-2 rounded border border-warning/30 bg-warning/5 p-3 text-sm">
            <div className="font-medium">These values are flagged but will be approved as-is:</div>
            <ul className="list-disc pl-5 text-xs">
              {warnings.map(w => (
                <li key={w.id}>
                  <span className="font-semibold">{w.name}</span>: <span className="font-mono">{w.value}</span>{' '}
                  <span className="text-muted-foreground">({w.state.replace(/_/g, ' ').toLowerCase()})</span>
                </li>
              ))}
            </ul>
            <label className="flex items-center gap-2 text-xs">
              <input type="checkbox" checked={acknowledged} onChange={e => setAcknowledged(e.target.checked)} />
              I confirm these values match the source document.
            </label>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>Cancel</Button>
          <Button
            variant={isReject ? "destructive" : "default"}
            className={!isReject ? "bg-success hover:bg-success/90 text-success-foreground" : ""}
            onClick={handleSubmit}
            disabled={!canSubmit || isSubmitting}
          >
            {isReject ? 'Confirm Rejection' : 'Approve Document'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
