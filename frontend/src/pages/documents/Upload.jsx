import React, { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { UploadCloud, X, CheckCircle2, Loader2, FileType2, Download, AlertCircle, Copy } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { uploadDocument } from '@/services/apiClient';
import { useDemoInfo, SAMPLE_REPORTS } from '@/lib/demo';

const VALID_TYPES = ['application/pdf', 'image/png', 'image/jpeg'];
const MAX_BYTES = 10 * 1024 * 1024;
// Files uploaded at the same time
const CONCURRENCY = 2;

let nextId = 0;

function newItem(file) {
  const item = { id: ++nextId, file, status: 'queued', progress: 0 };
  if (!VALID_TYPES.includes(file.type)) return { ...item, status: 'error', error: 'Not a PDF, PNG or JPG' };
  if (file.size > MAX_BYTES) return { ...item, status: 'error', error: 'Larger than 10 MB' };
  return item;
}

export function Upload() {
  const [items, setItems] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [running, setRunning] = useState(false);
  const inputRef = useRef(null);
  const queryClient = useQueryClient();
  const { data: demo } = useDemoInfo();

  const update = (id, changes) => setItems(prev => prev.map(it => (it.id === id ? { ...it, ...changes } : it)));

  const addFiles = (fileList) => {
    const added = Array.from(fileList || []).map(newItem);
    if (added.length) setItems(prev => [...prev, ...added]);
  };

  const uploadOne = async (item, allowDuplicate = false) => {
    update(item.id, { status: 'uploading', progress: 0, error: null });
    try {
      const doc = await uploadDocument(item.file, {
        allowDuplicate,
        onProgress: (progress) => update(item.id, { progress }),
      });
      update(item.id, { status: 'done', progress: 100, documentId: doc.id });
    } catch (err) {
      if (err.status === 409 && err.detail?.code === 'DUPLICATE_DOCUMENT') {
        update(item.id, { status: 'duplicate', error: err.detail.message, existingId: err.detail.existing_document_id });
      } else {
        update(item.id, { status: 'error', error: err.message || 'Upload failed' });
      }
    }
  };

  const uploadAll = async () => {
    const queue = items.filter(it => it.status === 'queued');
    setRunning(true);
    const workers = Array.from({ length: Math.min(CONCURRENCY, queue.length) }, async () => {
      while (queue.length) await uploadOne(queue.shift());
    });
    await Promise.all(workers);
    setRunning(false);
    queryClient.invalidateQueries({ queryKey: ['documents'] });
  };

  const uploadAnyway = async (item) => {
    await uploadOne(item, true);
    queryClient.invalidateQueries({ queryKey: ['documents'] });
  };

  const queued = items.filter(it => it.status === 'queued').length;
  const finished = items.filter(it => ['done', 'duplicate', 'error'].includes(it.status)).length;

  return (
    <div className="flex flex-col gap-6 max-w-3xl mx-auto w-full">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Upload Documents</h1>
        <p className="text-muted-foreground">Submit clinical documents for extraction. Several files can be uploaded at once.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Files</CardTitle>
          <CardDescription>PDF, PNG or JPG, up to 10 MB each. The same file is not processed twice.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div
            className={`border-2 border-dashed rounded-lg p-10 text-center transition-colors cursor-pointer ${
              isDragging ? 'border-primary bg-primary/5' : 'border-muted-foreground/25 hover:border-primary/50'
            }`}
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(e) => { e.preventDefault(); setIsDragging(false); addFiles(e.dataTransfer.files); }}
            onClick={() => inputRef.current?.click()}
            role="button"
            tabIndex={0}
            aria-label="Choose files to upload"
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                inputRef.current?.click();
              }
            }}
          >
            <UploadCloud className="mx-auto h-10 w-10 text-muted-foreground mb-3" />
            <h3 className="text-lg font-medium mb-1">Click or drag files here</h3>
            <p className="text-sm text-muted-foreground">Strictly use synthetic/fictitious healthcare data.</p>
            <input
              id="file-upload"
              ref={inputRef}
              type="file"
              multiple
              className="hidden"
              accept=".pdf,.png,.jpg,.jpeg"
              onChange={(e) => { addFiles(e.target.files); e.target.value = ''; }}
            />
          </div>

          {items.length > 0 && (
            <ul className="divide-y rounded-md border">
              {items.map(item => (
                <li key={item.id} className="flex items-center gap-3 p-3">
                  <FileType2 className="h-6 w-6 shrink-0 text-primary" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="truncate text-sm font-medium">{item.file.name}</p>
                      <span className="shrink-0 text-xs text-muted-foreground">{(item.file.size / 1024 / 1024).toFixed(2)} MB</span>
                    </div>
                    {item.status === 'uploading' && <Progress value={item.progress} className="mt-2 h-1.5" />}
                    {item.status === 'done' && (
                      <p className="mt-1 flex items-center gap-1 text-xs text-success">
                        <CheckCircle2 className="h-3.5 w-3.5" /> Uploaded and queued for processing ·{' '}
                        <Link className="underline" to={`/documents/${item.documentId}`}>View</Link>
                      </p>
                    )}
                    {item.status === 'duplicate' && (
                      <p className="mt-1 flex flex-wrap items-center gap-1 text-xs text-warning-foreground">
                        <Copy className="h-3.5 w-3.5" /> {item.error}{' '}
                        <Link className="underline" to={`/documents/${item.existingId}`}>Open it</Link>
                        <span>·</span>
                        <button type="button" className="underline" onClick={() => uploadAnyway(item)}>Upload anyway</button>
                      </p>
                    )}
                    {item.status === 'error' && (
                      <p className="mt-1 flex items-center gap-1 text-xs text-destructive">
                        <AlertCircle className="h-3.5 w-3.5" /> {item.error}
                      </p>
                    )}
                  </div>
                  {item.status === 'uploading' ? (
                    <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
                  ) : item.status === 'queued' && !running ? (
                    <Button variant="ghost" size="icon" aria-label={`Remove ${item.file.name}`}
                      onClick={() => setItems(prev => prev.filter(it => it.id !== item.id))}>
                      <X className="h-4 w-4" />
                    </Button>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
        {items.length > 0 && (
          <CardFooter className="flex justify-between gap-2 border-t p-4">
            <Button variant="ghost" disabled={running || finished === 0}
              onClick={() => setItems(prev => prev.filter(it => !['done', 'duplicate', 'error'].includes(it.status)))}>
              Clear finished
            </Button>
            <Button onClick={uploadAll} disabled={running || queued === 0}>
              {running ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
              {queued > 1 ? `Upload ${queued} files` : 'Upload and Process'}
            </Button>
          </CardFooter>
        )}
      </Card>

      {demo?.enabled && (
        <Card>
          <CardHeader>
            <CardTitle>Sample reports</CardTitle>
            <CardDescription>Synthetic lab reports. Download one, then upload it above to see how it is handled.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-2">
            {SAMPLE_REPORTS.map(sample => (
              <a key={sample.file} href={`/samples/${sample.file}`} download
                className="flex items-center gap-3 rounded-md border p-3 text-sm hover:bg-muted/50">
                <Download className="h-4 w-4 shrink-0 text-primary" />
                <span>
                  <span className="block font-medium font-mono text-xs">{sample.file}</span>
                  <span className="block text-muted-foreground">{sample.description}</span>
                </span>
              </a>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
