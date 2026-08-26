import React from 'react';
import { cn } from '@/lib/utils';

export function SyntheticDocumentViewer({ layout, activeBbox }) {
  if (!layout) return null;

  // Render a highlight box based on normalized coordinates [x, y, w, h] (percentages)
  const renderHighlight = (bbox, isActive = false) => {
    if (!bbox) return null;
    const [x, y, w, h] = bbox;
    return (
      <div 
        key={bbox.join(',')}
        className={cn(
          "absolute border-2 pointer-events-none transition-all duration-300",
          isActive ? "border-primary bg-primary/20 shadow-[0_0_0_4px_rgba(var(--primary),0.15)] z-20" 
                   : "border-warning/30 bg-warning/5 z-10 hidden" // Hide inactive by default for cleaner look, or subtle
        )}
        style={{
          left: `${x}%`,
          top: `${y}%`,
          width: `${w}%`,
          height: `${h}%`,
          display: isActive ? 'block' : 'none' // Only show active highlight to avoid clutter
        }}
      />
    );
  };

  const isBoxActive = (box) => {
    if (!box || !activeBbox) return false;
    return box.join(',') === activeBbox.join(',');
  };

  return (
    <div className="w-full max-w-[800px] min-h-[1000px] aspect-[8.5/11] bg-white shadow-lg border relative mx-auto my-4 p-[6%] text-slate-900 font-sans text-sm leading-relaxed">
      
      {/* HEADER */}
      {layout.header && (
        <div className="mb-8 border-b-2 border-slate-800 pb-6 text-center">
          <h1 className="text-2xl font-serif font-bold text-slate-900 uppercase tracking-widest">{layout.header.text}</h1>
          <p className="text-slate-600 text-xs mt-1">{layout.header.address} | {layout.header.phone}</p>
        </div>
      )}

      {/* METADATA BLOCK */}
      <div className="grid grid-cols-2 gap-8 mb-8">
        {/* Patient Info */}
        {layout.patientInfo && (
          <div className="border border-slate-200 p-3 bg-slate-50">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 border-b pb-1">Patient Details</h3>
            <div className="space-y-1">
              {layout.patientInfo.map((info, idx) => (
                <div key={idx} className="flex justify-between text-xs">
                  <span className="font-semibold text-slate-700">{info.label}</span>
                  <span className="font-mono">{info.value}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Specimen Info */}
        {layout.specimenInfo && (
          <div className="border border-slate-200 p-3 bg-slate-50">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 border-b pb-1">Specimen Details</h3>
            <div className="space-y-1">
              {layout.specimenInfo.map((info, idx) => (
                <div key={idx} className="flex justify-between text-xs">
                  <span className="font-semibold text-slate-700">{info.label}</span>
                  <span className="font-mono">{info.value}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* REPORT METADATA */}
      {layout.reportMetadata && (
        <div className="mb-6 flex justify-between text-xs font-bold text-slate-800 bg-slate-100 p-2 border-y border-slate-300">
          <span>{layout.reportMetadata.label}</span>
          <span>{layout.reportMetadata.value}</span>
        </div>
      )}

      {/* RESULTS TABLE */}
      {layout.resultsTable && (
        <div className="mb-10">
          <table className="w-full text-sm text-left border-collapse">
            <thead>
              <tr className="border-b-2 border-slate-400 text-slate-700 bg-slate-50">
                {layout.resultsTable.headers.map((h, i) => (
                  <th key={i} className="py-2 px-2 text-xs uppercase tracking-wider font-bold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {layout.resultsTable.rows.map((row, i) => (
                <tr key={i} className="border-b border-slate-200 hover:bg-slate-50/50">
                  <td className="py-2.5 px-2 font-medium text-slate-800">{row.test}</td>
                  <td className="py-2.5 px-2 font-mono font-bold text-slate-900">{row.result}</td>
                  <td className="py-2.5 px-2 text-slate-500 text-xs">{row.units}</td>
                  <td className="py-2.5 px-2 text-slate-500 text-xs font-mono">{row.range}</td>
                  <td className="py-2.5 px-2 text-red-600 font-bold text-center">{row.flag}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* INTERPRETATION */}
      {layout.interpretation && (
        <div className="mb-8 border-l-4 border-slate-400 pl-4 py-1">
          <h4 className="text-xs font-bold uppercase text-slate-700 mb-1">{layout.interpretation.title}</h4>
          <p className="text-slate-600 text-sm italic">{layout.interpretation.text}</p>
        </div>
      )}

      {/* FOOTER */}
      {layout.footer && (
        <div className="absolute bottom-6 left-[6%] right-[6%] border-t border-slate-300 pt-4 text-center text-[10px] text-slate-400 uppercase tracking-wide">
          {layout.footer.text}
        </div>
      )}

      {/* HIGHLIGHTS OVERLAY */}
      <div className="absolute inset-0 pointer-events-none">
        {/* Draw active highlight */}
        {layout.patientInfo?.map(info => renderHighlight(info.bbox, isBoxActive(info.bbox)))}
        {layout.specimenInfo?.map(info => renderHighlight(info.bbox, isBoxActive(info.bbox)))}
        {layout.resultsTable?.rows.map(row => renderHighlight(row.valBbox, isBoxActive(row.valBbox)))}
      </div>

    </div>
  );
}
