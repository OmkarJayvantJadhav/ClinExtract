import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Server, Database, Activity, Cpu, Bot, FileText, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { getDetailedHealth } from '@/services/apiClient';

export function SystemHealth() {
  const { data: health, isLoading, isError } = useQuery({
    queryKey: ['health-detailed'],
    queryFn: getDetailedHealth,
    refetchInterval: 15000,
  });

  const getIcon = (name) => {
    if (name.includes('API')) return <Server className="h-5 w-5" />;
    if (name.includes('Database')) return <Database className="h-5 w-5" />;
    if (name.includes('RabbitMQ')) return <Activity className="h-5 w-5" />;
    if (name.includes('Worker')) return <Cpu className="h-5 w-5" />;
    if (name.includes('Storage')) return <FileText className="h-5 w-5" />;
    return <Bot className="h-5 w-5" />;
  };

  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center p-8">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const status = isError ? "degraded" : (health?.status || "unavailable");
  const isHealthy = status === "healthy";
  const services = health?.dependencies ? Object.entries(health.dependencies).map(([k, v]) => ({
    name: k.charAt(0).toUpperCase() + k.slice(1),
    status: v,
    description: `Service status for ${k}`
  })) : [];

  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto w-full">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">System Health</h1>
          <p className="text-muted-foreground">Infrastructure operational status</p>
        </div>
        <div className="text-right text-sm">
          <div className="flex items-center gap-2 justify-end mb-1">
            <span className="relative flex h-3 w-3">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${isHealthy ? 'bg-success' : 'bg-warning'}`}></span>
              <span className={`relative inline-flex rounded-full h-3 w-3 ${isHealthy ? 'bg-success' : 'bg-warning'}`}></span>
            </span>
            <span className={`font-medium ${isHealthy ? 'text-success' : 'text-warning'}`}>{status.toUpperCase()}</span>
          </div>
          <p className="text-muted-foreground">Auto-refreshing</p>
        </div>
      </div>

      <h2 className="text-xl font-semibold mt-4">Core Services</h2>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {services.map(service => (
          <Card key={service.name} className={service.status !== 'healthy' ? 'border-warning bg-warning/5' : ''}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <div className="flex items-center gap-2">
                <div className="p-2 bg-secondary rounded-md">
                  {getIcon(service.name)}
                </div>
                <CardTitle className="text-base">{service.name}</CardTitle>
              </div>
              {service.status === 'healthy' 
                ? <CheckCircle2 className="h-5 w-5 text-success" /> 
                : <AlertTriangle className="h-5 w-5 text-warning" />
              }
            </CardHeader>
            <CardContent>
              <CardDescription className="mb-4">{service.description}</CardDescription>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Status</span>
                <span className={`font-medium capitalize ${service.status !== 'healthy' ? 'text-warning-foreground' : 'text-success'}`}>{service.status}</span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
