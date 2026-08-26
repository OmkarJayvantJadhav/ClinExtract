import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Legend } from 'recharts';
import { useQuery } from '@tanstack/react-query';
import { getAnalytics } from '@/services/apiClient';
import { useAuth } from '@/context/AuthContext';
import { Loader2 } from 'lucide-react';

const COLORS = {
  success: 'hsl(var(--success))',
  warning: 'hsl(var(--warning))',
  destructive: 'hsl(var(--destructive))',
  primary: 'hsl(var(--primary))',
  muted: 'hsl(var(--muted))'
};

const mapStatusToColor = (statusName) => {
  if (statusName.includes('ACCEPTED') || statusName.includes('APPROVED')) return COLORS.success;
  if (statusName.includes('REVIEW')) return COLORS.warning;
  if (statusName.includes('REJECTED')) return COLORS.destructive;
  if (statusName.includes('FAILED')) return COLORS.muted;
  return COLORS.primary;
};

export function Analytics() {
  const { user } = useAuth();
  
  const { data: analytics, isLoading } = useQuery({
    queryKey: ['analytics'],
    queryFn: getAnalytics,
    enabled: user?.role === 'ADMIN' || user?.role === 'SUPERVISOR',
    refetchInterval: 60000
  });

  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center p-8">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Default if unauthorized or failing
  const stats = analytics || {
    documents: { total: 0 },
    review: { correction_rate: 0 },
    distributions: { status: [], type: [], confidence: [] }
  };
  
  const statusDistribution = stats.distributions?.status.map(s => ({...s, name: s.name.replace('DocumentStatus.', '')})) || [];
  const typeDistribution = stats.distributions?.type || [];
  const confidenceDistribution = stats.distributions?.confidence || [];

  return (
    <div className="flex flex-col gap-6 w-full h-full">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Analytics</h1>
        <p className="text-muted-foreground">Extraction quality and workforce efficiency metrics.</p>
      </div>

      {/* KPI Row */}
      <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-6">
        {[
          { label: "Total Processed", value: stats.documents.total },
          { label: "Human Correction", value: `${(stats.review.correction_rate * 100).toFixed(1)}%` },
          { label: "Avg Confidence", value: "N/A" },
          { label: "Avg Review Time", value: "N/A" },
          { label: "Fallback Operations", value: stats.extraction?.fallback_count || 0 },
          { label: "Auto Accept Vol", value: stats.validation?.auto_accepted || 0 }
        ].map((k, i) => (
          <Card key={i}>
            <CardHeader className="p-4 pb-2">
              <CardTitle className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">{k.label}</CardTitle>
            </CardHeader>
            <CardContent className="p-4 pt-0">
              <div className="text-2xl font-bold font-mono">{k.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Charts Grid */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Processing Workflow Routing</CardTitle>
          </CardHeader>
          <CardContent className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={statusDistribution}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={2}
                  dataKey="value"
                >
                  {statusDistribution.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={mapStatusToColor(entry.name)} />
                  ))}
                </Pie>
                <RechartsTooltip contentStyle={{ borderRadius: '8px', border: '1px solid hsl(var(--border))' }} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Extraction Confidence</CardTitle>
          </CardHeader>
          <CardContent className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={confidenceDistribution} layout="vertical" margin={{ top: 0, right: 30, left: 20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} />
                <XAxis type="number" />
                <YAxis dataKey="name" type="category" width={80} tick={{fontSize: 12}} />
                <RechartsTooltip cursor={{fill: 'hsl(var(--muted)/0.5)'}} />
                <Bar dataKey="count" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>Document Type Volume</CardTitle>
          </CardHeader>
          <CardContent className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={typeDistribution} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" tick={{fontSize: 12}} />
                <YAxis />
                <RechartsTooltip cursor={{fill: 'hsl(var(--muted)/0.5)'}} />
                <Bar dataKey="value" fill="hsl(var(--secondary-foreground))" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
