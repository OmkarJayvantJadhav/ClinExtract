import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { fetchApi } from '@/services/apiClient';

/** Admin-only permanent deletion with a mandatory reason (recorded in the audit log). */
export function DeleteDocumentDialog({ document, open, onOpenChange, onDeleted }) {
  const [reason, setReason] = useState('');
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => fetchApi(`/documents/${document.id}?reason=${encodeURIComponent(reason.trim())}`, { method: 'DELETE' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      queryClient.removeQueries({ queryKey: ['document', document.id] });
      onOpenChange(false);
      onDeleted?.();
    },
  });

  if (!document) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete document permanently?</DialogTitle>
          <DialogDescription>
            <span className="font-mono">{document.filename}</span> and all extracted data, reviews and stored files will be removed.
            The audit trail is kept with patient data redacted. This cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-2 py-2">
          <Label htmlFor="delete-reason">Reason *</Label>
          <Input id="delete-reason" value={reason} onChange={e => setReason(e.target.value)} placeholder="e.g. uploaded in error, patient erasure request" />
        </div>
        {mutation.isError && <p className="text-sm text-destructive">{mutation.error.message}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={mutation.isPending}>Cancel</Button>
          <Button variant="destructive" onClick={() => mutation.mutate()} disabled={reason.trim().length < 3 || mutation.isPending}>
            Delete permanently
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
