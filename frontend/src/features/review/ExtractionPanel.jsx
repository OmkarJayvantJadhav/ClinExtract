import React from 'react';
import { EditableField } from './EditableField';

export function ExtractionPanel({ extraction, corrections, onFieldSelect, onFieldEdit }) {
  const renderSection = (title, fields) => {
    if (!fields || fields.length === 0) return null;
    return (
      <div className="mb-8">
        <div className="bg-muted/50 px-4 py-2 border-y border-border">
          <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-widest">{title}</h3>
        </div>
        <div className="flex flex-col">
          {fields.map(field => (
            <EditableField 
              key={field.id} 
              field={field} 
              currentValue={corrections[field.id] !== undefined ? corrections[field.id] : field.value}
              isCorrected={corrections[field.id] !== undefined}
              onSelect={() => onFieldSelect(field)}
              onEdit={(val) => onFieldEdit(field.id, val)}
            />
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="w-full pb-8">
      {renderSection("Patient Information", extraction.patientInfo)}
      {renderSection("Document Information", extraction.documentInfo)}
      {renderSection("Laboratory Results", extraction.laboratoryResults)}
    </div>
  );
}
