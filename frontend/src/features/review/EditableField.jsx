import React, { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Check, X, RotateCcw } from 'lucide-react';
import { ValidationBadge } from '@/components/common/StatusPrimitives';

// Mounted only while editing, so it always starts from the field's current value
function FieldEditor({ initialValue, onSave, onCancel }) {
  const [tempValue, setTempValue] = useState(initialValue);
  return (
    <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
      <Input
        autoFocus
        className="h-8 text-sm font-mono border-primary shadow-xs"
        value={tempValue ?? ''}
        onChange={(e) => setTempValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') onSave(tempValue);
          if (e.key === 'Escape') onCancel();
        }}
      />
      <Button size="icon" variant="ghost" className="h-8 w-8 text-success hover:text-success hover:bg-success/10" onClick={() => onSave(tempValue)}>
        <Check className="h-4 w-4" />
      </Button>
      <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground hover:bg-destructive/10 hover:text-destructive" onClick={onCancel}>
        <X className="h-4 w-4" />
      </Button>
    </div>
  );
}

export function EditableField({ field, currentValue, isCorrected, isActive, isEditing, onEditingChange, onSelect, onEdit }) {
  const ref = useRef(null);

  // Keep the field selected from the keyboard in view
  useEffect(() => {
    if (isActive) ref.current?.scrollIntoView?.({ block: 'nearest' });
  }, [isActive]);

  const handleSave = (tempValue) => {
    const original = field.value ?? '';
    if ((tempValue ?? '') !== original) {
      onEdit(tempValue);
    } else {
      // Reverted to original
      onEdit(undefined);
    }
    onEditingChange(false);
  };

  const handleCancel = () => onEditingChange(false);

  const handleRevert = (e) => {
    e.stopPropagation();
    onEdit(undefined);
  };

  // Determine current validation state logic
  // If user corrected it, show 'CORRECTED'. Otherwise show the original state.
  const displayState = isCorrected ? 'CORRECTED' : field.state;

  return (
    <div
      ref={ref}
      className={cn(
        "group flex flex-col py-2 px-3 border-b border-border/50 hover:bg-muted/30 cursor-pointer transition-colors relative",
        isCorrected && "bg-primary/5",
        isActive && "ring-2 ring-inset ring-primary/40"
      )}
      onClick={() => { if (!isEditing) onSelect(); }}
    >
      <div className="flex justify-between items-start mb-0.5">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{field.name}</span>
        <div className="flex items-center gap-2">
          {/* Validation Badge */}
          <ValidationBadge state={displayState} message={!isCorrected && field.validationMessage} />

          {/* Confidence Score (Hidden if corrected, since human replaced AI) */}
          {!isCorrected && field.confidence !== null && field.confidence !== undefined && (
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
          <FieldEditor initialValue={currentValue} onSave={handleSave} onCancel={handleCancel} />
        ) : (
          <div 
            className="flex items-center justify-between min-h-[28px]"
            onDoubleClick={(e) => {
              e.stopPropagation();
              onSelect();
              onEditingChange(true);
            }}
          >
            <div className="flex items-baseline gap-1.5">
              <span className={cn("text-sm font-mono", isCorrected ? "font-bold text-primary" : "text-foreground")}>
                {currentValue === null || currentValue === undefined || currentValue === '' ? <span className="italic text-muted-foreground">— not extracted —</span> : currentValue}
              </span>
              {field.unit && <span className="text-xs text-muted-foreground font-mono">{field.unit}</span>}
              {field.abnormalFlag && <span className="text-xs font-semibold text-warning-foreground">{field.abnormalFlag}</span>}
              {field.referenceRange && <span className="text-xs text-muted-foreground">(ref {field.referenceRange})</span>}
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
          <span className="text-muted-foreground">Originally extracted: <span className="line-through font-mono ml-1">{field.value ?? '(empty)'}</span></span>
          <Button variant="ghost" size="sm" className="h-5 px-1.5 text-xs text-muted-foreground hover:text-destructive" onClick={handleRevert}>
            <RotateCcw className="h-3 w-3 mr-1" /> Revert
          </Button>
        </div>
      )}
    </div>
  );
}
