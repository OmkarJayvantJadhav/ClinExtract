import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Check, X, RotateCcw } from 'lucide-react';
import { ValidationBadge } from '@/components/common/StatusPrimitives';

export function EditableField({ field, currentValue, isCorrected, onSelect, onEdit }) {
  const [isEditing, setIsEditing] = useState(false);
  const [tempValue, setTempValue] = useState(currentValue);

  const handleSave = () => {
    if (tempValue !== field.value) {
      onEdit(tempValue);
    } else {
      // Reverted to original
      onEdit(undefined); 
    }
    setIsEditing(false);
  };

  const handleCancel = () => {
    setTempValue(currentValue);
    setIsEditing(false);
  };

  const handleRevert = (e) => {
    e.stopPropagation();
    onEdit(undefined);
  };

  // Determine current validation state logic
  // If user corrected it, show 'CORRECTED'. Otherwise show the original state.
  const displayState = isCorrected ? 'CORRECTED' : field.state;

  return (
    <div 
      className={cn(
        "group flex flex-col py-2 px-3 border-b border-border/50 hover:bg-muted/30 cursor-pointer transition-colors relative",
        isCorrected && "bg-primary/5"
      )}
      onClick={() => { if (!isEditing) onSelect(); }}
    >
      <div className="flex justify-between items-start mb-0.5">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{field.name}</span>
        <div className="flex items-center gap-2">
          {/* Validation Badge */}
          <ValidationBadge state={displayState} message={!isCorrected && field.validationMessage} />

          {/* Confidence Score (Hidden if corrected, since human replaced AI) */}
          {!isCorrected && (
            <span className={cn(
              "text-[10px] font-mono px-1.5 py-0.5 rounded",
              field.confidence >= 90 ? "bg-success/10 text-success-foreground" :
              field.confidence >= 70 ? "bg-warning/10 text-warning-foreground" :
              "bg-destructive/10 text-destructive"
            )}>{field.confidence}%</span>
          )}
        </div>
      </div>

      <div className="mt-1">
        {isEditing ? (
          <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
            <Input 
              autoFocus
              className="h-8 text-sm font-mono border-primary shadow-sm"
              value={tempValue}
              onChange={(e) => setTempValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSave();
                if (e.key === 'Escape') handleCancel();
              }}
            />
            <Button size="icon" variant="ghost" className="h-8 w-8 text-success hover:text-success hover:bg-success/10" onClick={handleSave}>
              <Check className="h-4 w-4" />
            </Button>
            <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground hover:bg-destructive/10 hover:text-destructive" onClick={handleCancel}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        ) : (
          <div 
            className="flex items-center justify-between min-h-[28px]"
            onDoubleClick={(e) => {
              e.stopPropagation();
              setTempValue(currentValue);
              setIsEditing(true);
            }}
          >
            <div className="flex items-baseline gap-1.5">
              <span className={cn("text-sm font-mono", isCorrected ? "font-bold text-primary" : "text-foreground")}>
                {currentValue}
              </span>
              {field.unit && <span className="text-xs text-muted-foreground font-mono">{field.unit}</span>}
            </div>
            
            <div className="flex flex-col items-end gap-1">
               {/* Hover Edit Hint */}
              <span className="text-[9px] text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity uppercase tracking-wider font-semibold">
                Double-click to edit
              </span>
            </div>
          </div>
        )}
      </div>

      {isCorrected && !isEditing && (
        <div className="mt-1.5 flex items-center justify-between text-[11px] bg-muted/50 p-1.5 rounded-sm">
          <span className="text-muted-foreground">Original AI extraction: <span className="line-through font-mono ml-1">{field.value}</span></span>
          <Button variant="ghost" size="sm" className="h-5 px-1.5 text-xs text-muted-foreground hover:text-destructive" onClick={handleRevert}>
            <RotateCcw className="h-3 w-3 mr-1" /> Revert
          </Button>
        </div>
      )}
    </div>
  );
}
