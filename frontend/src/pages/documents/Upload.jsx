import React, { useState } from 'react';
import { UploadCloud, X, CheckCircle2, Loader2, FileType2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Link } from 'react-router-dom';

export function Upload() {
  const [file, setFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [docType, setDocType] = useState('Laboratory Report');
  const [uploadedId, setUploadedId] = useState(null);
  
  // Upload states
  const [uploadStatus, setUploadStatus] = useState('IDLE'); // IDLE, UPLOADING, SUCCESS, ERROR
  const [progress, setProgress] = useState(0);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (selectedFile) => {
    const validTypes = ['application/pdf', 'image/png', 'image/jpeg'];
    if (!validTypes.includes(selectedFile.type)) {
      alert("Invalid file type. Please upload a PDF, PNG, or JPG.");
      return;
    }
    if (selectedFile.size > 10 * 1024 * 1024) {
      alert("File is too large. Maximum size is 10MB.");
      return;
    }
    setFile(selectedFile);
    setUploadStatus('IDLE');
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploadStatus('UPLOADING');
    setProgress(0);
    
    // Quick pseudo-progress simulation
    const interval = setInterval(() => {
      setProgress(p => Math.min(p + 15, 90));
    }, 200);

    try {
      const formData = new FormData();
      formData.append('file', file);
      // If backend accepted docType we could pass it here too
      
      const { fetchApi } = await import('@/services/apiClient');
      const responseData = await fetchApi('/documents', {
        method: 'POST',
        body: formData
      });

      clearInterval(interval);
      setProgress(100);
      setUploadedId(responseData.id);
      setUploadStatus('SUCCESS');
    } catch (err) {
      clearInterval(interval);
      setUploadStatus('IDLE');
      alert(err.message || 'Upload failed');
    }
  };

  const reset = () => {
    setFile(null);
    setUploadStatus('IDLE');
    setProgress(0);
  };

  return (
    <div className="flex flex-col gap-6 max-w-3xl mx-auto w-full">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Upload Document</h1>
        <p className="text-muted-foreground">Submit clinical documents for intelligent extraction.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>File Upload</CardTitle>
          <CardDescription>Supported formats: PDF, PNG, JPG (Max 10MB)</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          
          {uploadStatus === 'IDLE' && (
            <div 
              className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors cursor-pointer ${
                isDragging ? 'border-primary bg-primary/5' : 'border-muted-foreground/25 hover:border-primary/50'
              }`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => document.getElementById('file-upload').click()}
            >
              <UploadCloud className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-1">Click or drag file to this area to upload</h3>
              <p className="text-sm text-muted-foreground">Strictly use synthetic/fictitious healthcare data.</p>
              <input 
                id="file-upload" 
                type="file" 
                className="hidden" 
                accept=".pdf,.png,.jpg,.jpeg" 
                onChange={handleFileChange} 
              />
            </div>
          )}

          {file && uploadStatus === 'IDLE' && (
            <div className="space-y-4 animate-in fade-in duration-300">
              <div className="flex items-center justify-between p-4 border rounded-md bg-muted/30">
                <div className="flex items-center gap-3">
                  <FileType2 className="h-8 w-8 text-primary" />
                  <div>
                    <p className="font-medium text-sm">{file.name}</p>
                    <p className="text-xs text-muted-foreground">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                  </div>
                </div>
                <Button variant="ghost" size="icon" onClick={reset}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
              
              <div className="space-y-2">
                <Label>Document Type</Label>
                <Select value={docType} onValueChange={setDocType}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Laboratory Report">Laboratory Report</SelectItem>
                    <SelectItem value="Laboratory Requisition">Laboratory Requisition</SelectItem>
                    <SelectItem value="Diagnostic Report">Diagnostic Report</SelectItem>
                    <SelectItem value="General Clinical Document">General Clinical Document</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}

          {uploadStatus === 'UPLOADING' && (
            <div className="py-8 space-y-4 text-center">
              <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
              <div className="space-y-2 max-w-sm mx-auto">
                <div className="flex justify-between text-sm">
                  <span>Uploading {file.name}...</span>
                  <span>{progress}%</span>
                </div>
                <Progress value={progress} />
              </div>
            </div>
          )}

          {uploadStatus === 'SUCCESS' && (
            <div className="py-12 text-center animate-in zoom-in-95 duration-300">
              <div className="mx-auto w-16 h-16 bg-success/20 rounded-full flex items-center justify-center mb-4">
                <CheckCircle2 className="h-8 w-8 text-success" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Upload Successful</h3>
              <p className="text-muted-foreground mb-6">
                Document has been queued for processing.
              </p>
              <div className="flex justify-center gap-4">
                <Button variant="outline" onClick={reset}>Upload Another</Button>
                <Button asChild>
                  <Link to={`/documents/${uploadedId}`}>View Processing Status</Link>
                </Button>
              </div>
            </div>
          )}

        </CardContent>
        {uploadStatus === 'IDLE' && (
          <CardFooter className="flex justify-end border-t p-4">
            <Button onClick={handleUpload} disabled={!file}>
              Upload and Process
            </Button>
          </CardFooter>
        )}
      </Card>
    </div>
  );
}
