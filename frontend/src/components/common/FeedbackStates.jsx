import React from 'react';
import { Loader2, AlertCircle, FileX2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function LoadingState({ message = "Loading...", className }) {
  return (
    <div className={`flex flex-col items-center justify-center p-8 text-center animate-in fade-in duration-500 ${className}`}>
      <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
      <p className="text-sm font-medium text-muted-foreground">{message}</p>
    </div>
  );
}

export function ErrorState({ title = "Something went wrong", message, onRetry, className }) {
  return (
    <div className={`flex flex-col items-center justify-center p-8 text-center border rounded-lg bg-destructive/5 ${className}`}>
      <div className="rounded-full bg-destructive/10 p-3 mb-4">
        <AlertCircle className="h-6 w-6 text-destructive" />
      </div>
      <h3 className="text-lg font-semibold text-foreground mb-2">{title}</h3>
      {message && <p className="text-sm text-muted-foreground mb-4 max-w-md">{message}</p>}
      {onRetry && (
        <Button variant="outline" onClick={onRetry}>
          Try Again
        </Button>
      )}
    </div>
  );
}

export function EmptyState({ title = "No data found", message, action, icon: Icon = FileX2, className }) {
  return (
    <div className={`flex flex-col items-center justify-center p-12 text-center border border-dashed rounded-lg bg-muted/10 ${className}`}>
      <div className="rounded-full bg-secondary p-4 mb-4">
        <Icon className="h-8 w-8 text-secondary-foreground" />
      </div>
      <h3 className="text-lg font-semibold text-foreground mb-2">{title}</h3>
      {message && <p className="text-sm text-muted-foreground mb-6 max-w-sm">{message}</p>}
      {action && action}
    </div>
  );
}
