import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ConfidenceIndicator } from '@/components/common/StatusPrimitives';
import { EmptyState } from '@/components/common/FeedbackStates';
import { Edit, Clock, AlertCircle } from 'lucide-react';

import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '@/services/apiClient';
import { Loader2 } from 'lucide-react';

export function ReviewQueue() {
  const navigate = useNavigate();
  const [tab, setTab] = useState('pending');

  const { data: documentsData, isLoading } = useQuery({
    queryKey: ['documents', { status: 'REVIEW_REQUIRED' }],
    queryFn: () => fetchApi('/documents?status=REVIEW_REQUIRED&size=50'),
    refetchInterval: 10000
  });

  if (isLoading) {
    return <div className="flex h-[50vh] items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>;
  }

  const reviewDocs = documentsData?.items || [];
  
  // Fake tabs logic
  const getFilteredDocs = () => {
    switch (tab) {
      case 'high-priority': return reviewDocs.filter(d => d.priority === 'High');
      case 'low-confidence': return reviewDocs.filter(d => d.confidence < 70);
      case 'pending':
      default: return reviewDocs;
    }
  };

  const docsToDisplay = getFilteredDocs();

  return (
    <div className="flex flex-col gap-6 w-full h-full">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Review Queue</h1>
        <p className="text-muted-foreground">Prioritized list of documents requiring human validation.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="bg-primary/5 border-primary/20">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-primary">Pending Review</p>
              <h3 className="text-2xl font-bold">{reviewDocs.length}</h3>
            </div>
            <div className="h-10 w-10 bg-primary/10 rounded-full flex items-center justify-center">
              <Clock className="h-5 w-5 text-primary" />
            </div>
          </CardContent>
        </Card>
        <Card className="bg-warning/10 border-warning/20">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-warning-foreground">High Priority</p>
              <h3 className="text-2xl font-bold">{reviewDocs.filter(d => d.priority === 'High').length}</h3>
            </div>
            <div className="h-10 w-10 bg-warning/20 rounded-full flex items-center justify-center">
              <AlertCircle className="h-5 w-5 text-warning-foreground" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Average Confidence</p>
              <h3 className="text-2xl font-bold">
                {reviewDocs.length > 0 ? Math.round(reviewDocs.reduce((acc, d) => acc + (d.confidence || 0), 0) / reviewDocs.length) : 0}%
              </h3>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="flex-1 flex flex-col">
        <Tabs value={tab} onValueChange={setTab} className="flex-1 flex flex-col">
          <div className="p-4 border-b">
            <TabsList>
              <TabsTrigger value="pending">All Pending</TabsTrigger>
              <TabsTrigger value="high-priority">High Priority</TabsTrigger>
              <TabsTrigger value="low-confidence">Low Confidence</TabsTrigger>
            </TabsList>
          </div>
          
          <TabsContent value={tab} className="flex-1 p-0 m-0 overflow-auto">
            {docsToDisplay.length === 0 ? (
              <div className="py-20">
                <EmptyState title="Queue Empty" message="No documents match this filter." />
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Priority</TableHead>
                    <TableHead>Document</TableHead>
                    <TableHead>Patient</TableHead>
                    <TableHead>Confidence</TableHead>
                    <TableHead>Age</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {docsToDisplay.map((doc) => (
                    <TableRow key={doc.id}>
                      <TableCell>
                        {doc.priority === 'High' ? (
                          <span className="inline-flex items-center rounded-full bg-warning/20 px-2 py-0.5 text-xs font-medium text-warning-foreground">High</span>
                        ) : (
                          <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">Normal</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="font-medium">{doc.id}</div>
                        <div className="text-xs text-muted-foreground">{doc.type}</div>
                      </TableCell>
                      <TableCell>{doc.patientId}</TableCell>
                      <TableCell><ConfidenceIndicator score={doc.confidence} /></TableCell>
                      <TableCell className="text-muted-foreground text-sm">2 hrs</TableCell>
                      <TableCell className="text-right">
                        <Button size="sm" onClick={() => navigate(`/review/workspace/${doc.id}`)}>
                          <Edit className="h-4 w-4 mr-2" /> Start Review
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </TabsContent>
        </Tabs>
      </Card>
    </div>
  );
}
