import React, { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';

export function DecisionDialogs({ open, onOpenChange, type, onSubmit }) {
  const [reason, setReason] = useState('');
  const [comment, setComment] = useState('');
  const isReject = type === 'REJECT';

  const handleSubmit = () => {
    onSubmit(isReject ? `${reason}: ${comment}` : 'Approved by reviewer');
    setReason('');
    setComment('');
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isReject ? 'Reject Document' : 'Approve Document'}</DialogTitle>
          <DialogDescription>
            {isReject 
              ? 'Please provide a reason for rejecting this document extraction.' 
              : 'By approving, you confirm that all fields are correct and validation issues have been addressed.'}
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

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button 
            variant={isReject ? "destructive" : "default"}
            className={!isReject ? "bg-success hover:bg-success/90 text-success-foreground" : ""}
            onClick={handleSubmit}
            disabled={isReject && !reason}
          >
            {isReject ? 'Confirm Rejection' : 'Approve Document'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
