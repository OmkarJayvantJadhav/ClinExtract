import React, { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Loader2, ImageOff } from 'lucide-react';
import { apiUrl, fetchApi } from '@/services/apiClient';
import { cn } from '@/lib/utils';

/**
 * Renders the real uploaded document, one image per page (served by the backend in the
 * same coordinate frame as the extraction bounding boxes), and highlights the active field.
 *
 * activeField: { page_num, bbox: [x, y, w, h] as 0..1 fractions of the page } | null
 */
export function DocumentViewer({ documentId, activeField }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['document-pages', documentId],
    queryFn: () => fetchApi(`/documents/${documentId}/pages`),
    staleTime: Infinity,
  });

  if (isLoading) {
    return (
      <div className="flex h-64 w-full items-center justify-center text-muted-foreground">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-64 w-full flex-col items-center justify-center gap-2 text-sm text-destructive">
        <ImageOff className="h-6 w-6" />
        Unable to load the document: {error.message}
      </div>
    );
  }

  const pageCount = data?.page_count || 1;
  return (
    <div className="flex w-full max-w-[900px] flex-col gap-6">
      {Array.from({ length: pageCount }, (_, i) => i + 1).map((pageNum) => (
        <DocumentPage
          key={pageNum}
          documentId={documentId}
          pageNum={pageNum}
          pageCount={pageCount}
          activeBbox={(activeField?.page_num || 1) === pageNum ? activeField?.bbox : null}
        />
      ))}
    </div>
  );
}

function DocumentPage({ documentId, pageNum, pageCount, activeBbox }) {
  const [status, setStatus] = useState('loading');
  const highlightRef = useRef(null);

  useEffect(() => {
    if (activeBbox && status === 'loaded' && highlightRef.current) {
      highlightRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [activeBbox, status]);

  const [x, y, w, h] = activeBbox || [];
  const hasBox = Array.isArray(activeBbox) && activeBbox.length === 4;

  return (
    <div className="relative w-full border bg-white shadow-lg">
      {status === 'loading' && (
        <div className="absolute inset-0 flex min-h-[400px] items-center justify-center text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      )}
      {status === 'error' && (
        <div className="flex min-h-[200px] items-center justify-center text-sm text-destructive">
          Page {pageNum} could not be rendered.
        </div>
      )}
      <img
        src={apiUrl(`/documents/${documentId}/pages/${pageNum}/image`)}
        alt={`Document page ${pageNum} of ${pageCount}`}
        className={cn('block h-auto w-full select-none', status !== 'loaded' && 'invisible')}
        onLoad={() => setStatus('loaded')}
        onError={() => setStatus('error')}
        draggable={false}
      />
      {hasBox && status === 'loaded' && (
        <div
          ref={highlightRef}
          className="pointer-events-none absolute z-20 border-2 border-primary bg-primary/20 transition-all duration-300"
          style={{
            left: `${x * 100}%`,
            top: `${y * 100}%`,
            width: `${w * 100}%`,
            height: `${h * 100}%`,
            // Keep tiny word boxes visible
            minWidth: 6,
            minHeight: 6,
          }}
        />
      )}
      {pageCount > 1 && (
        <div className="absolute right-2 top-2 rounded bg-black/60 px-2 py-0.5 text-[10px] font-medium text-white">
          {pageNum} / {pageCount}
        </div>
      )}
    </div>
  );
}
