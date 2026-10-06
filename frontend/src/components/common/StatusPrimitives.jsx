import React from 'react';
import { cn } from '@/lib/utils';
import { CheckCircle2, AlertTriangle, AlertCircle, HelpCircle, XCircle, ShieldCheck } from 'lucide-react';

export function DocumentStatusBadge({ status }) {
  const getStatusConfig = () => {
    switch (status) {
      case 'AUTO_ACCEPTED':
        return { label: 'Auto Accepted', className: 'bg-success/15 text-success-foreground border-success/30', icon: CheckCircle2 };
      case 'HUMAN_APPROVED':
        return { label: 'Human Approved', className: 'bg-primary/15 text-primary border-primary/30', icon: ShieldCheck };
      case 'REVIEW_REQUIRED':
        return { label: 'Review Required', className: 'bg-warning/15 text-warning-foreground border-warning/30', icon: AlertTriangle };
      case 'PROCESSING':
        return { label: 'Processing', className: 'bg-info/15 text-info-foreground border-info/30', icon: HelpCircle };
      case 'FAILED':
      case 'HUMAN_REJECTED':
        return { label: status === 'FAILED' ? 'Failed' : 'Rejected', className: 'bg-destructive/15 text-destructive border-destructive/30', icon: XCircle };
      default:
        return { label: status || 'Unknown', className: 'bg-muted text-muted-foreground border-muted-foreground/30', icon: HelpCircle };
    }
  };

  const { label, className, icon: Icon } = getStatusConfig();

  return (
    <span className={cn("inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-xs font-medium border", className)}>
      <Icon className="h-3.5 w-3.5" />
      {label}
    </span>
  );
}

export function ConfidenceIndicator({ score, className }) {
  if (score === null || score === undefined) return <span className="text-muted-foreground text-sm">-</span>;
  
  // Semantic hierarchy
  let level = 'LOW CONFIDENCE';
  let colorClass = 'text-destructive';
  let bgClass = 'bg-destructive/20';
  let Icon = AlertCircle;

  if (score >= 90) {
    level = 'HIGH CONFIDENCE';
    colorClass = 'text-success-foreground';
    bgClass = 'bg-success/20';
    Icon = CheckCircle2;
  } else if (score >= 70) {
    level = 'REVIEW RECOMMENDED';
    colorClass = 'text-warning-foreground';
    bgClass = 'bg-warning/20';
    Icon = AlertTriangle;
  }

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <div className="flex items-center gap-2">
        <Icon className={cn("h-4 w-4", colorClass)} />
        <span className={cn("text-xs font-bold tracking-tight", colorClass)}>{score}%</span>
        <span className="text-[10px] font-semibold tracking-wider uppercase text-muted-foreground">{level}</span>
      </div>
      {/* Subtle indicator bar */}
      <div className="h-1.5 w-full bg-muted overflow-hidden rounded-sm">
        <div className={cn("h-full", bgClass)} style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}

export function ValidationBadge({ state, message }) {
  if (!state || state === 'VALID') return null;

  const config = {
    'SOURCE_MISMATCH': { color: 'text-destructive', bg: 'bg-destructive/10', border: 'border-destructive/20', icon: AlertCircle, label: 'Source Mismatch' },
    'OUTSIDE_REFERENCE_RANGE': { color: 'text-warning-foreground', bg: 'bg-warning/10', border: 'border-warning/20', icon: AlertTriangle, label: 'Outside Reference Range' },
    'INVALID_FORMAT': { color: 'text-destructive', bg: 'bg-destructive/10', border: 'border-destructive/20', icon: XCircle, label: 'Invalid Format' },
    'MISSING': { color: 'text-destructive', bg: 'bg-destructive/10', border: 'border-destructive/20', icon: XCircle, label: 'Missing' },
    'IMPLAUSIBLE_VALUE': { color: 'text-destructive', bg: 'bg-destructive/10', border: 'border-destructive/20', icon: XCircle, label: 'Implausible Value' },
    'UNRECOGNIZED_UNIT': { color: 'text-warning-foreground', bg: 'bg-warning/10', border: 'border-warning/20', icon: AlertTriangle, label: 'Unrecognized Unit' },
    'INCONSISTENT_DATES': { color: 'text-warning-foreground', bg: 'bg-warning/10', border: 'border-warning/20', icon: AlertTriangle, label: 'Inconsistent Dates' },
    'CORRECTED': { color: 'text-primary', bg: 'bg-primary/10', border: 'border-primary/20', icon: ShieldCheck, label: 'Corrected' }
  };

  const current = config[state] || { color: 'text-muted-foreground', bg: 'bg-muted', border: 'border-border', icon: HelpCircle, label: state };
  const Icon = current.icon;

  return (
    <div className="flex items-start gap-1 mt-1">
      <span className={cn("inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium border uppercase tracking-wide", current.bg, current.color, current.border)}>
        <Icon className="h-3 w-3" />
        {current.label}
      </span>
      {message && <span className="text-[11px] text-muted-foreground leading-tight mt-0.5 ml-1">{message}</span>}
    </div>
  );
}
