import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export function Settings() {
  return (
    <div className="flex flex-col gap-6 max-w-4xl mx-auto w-full">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">Manage personal profile and system configurations.</p>
      </div>

      <Tabs defaultValue="confidence" className="w-full">
        <TabsList className="grid w-full grid-cols-2 md:w-[400px]">
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="confidence">Confidence Thresholds</TabsTrigger>
        </TabsList>
        
        <TabsContent value="profile" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Profile Details</CardTitle>
              <CardDescription>Manage your user identity and preferences.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-2">
                <Label>Full Name</Label>
                <Input defaultValue="Demo Admin" />
              </div>
              <div className="grid gap-2">
                <Label>Email</Label>
                <Input defaultValue="demo@clinextract.system" disabled />
              </div>
              <Button className="mt-4">Save Profile</Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="confidence" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Global Confidence Thresholds</CardTitle>
              <CardDescription>
                Configure the AI confidence score routing behaviors. 
                <span className="block mt-2 font-medium text-destructive">These thresholds control workflow routing and are not clinical safety thresholds.</span>
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                <div className="grid gap-2">
                  <Label>High Confidence Threshold (%)</Label>
                  <p className="text-xs text-muted-foreground">Scores at or above this value will be eligible for Auto Acceptance (if business rules validate).</p>
                  <Input type="number" defaultValue="90" min="0" max="100" className="w-[150px]" />
                </div>
                <div className="grid gap-2">
                  <Label>Review Recommended Threshold (%)</Label>
                  <p className="text-xs text-muted-foreground">Scores below this value strictly require human review.</p>
                  <Input type="number" defaultValue="70" min="0" max="100" className="w-[150px]" />
                </div>
              </div>
              <Button>Save Configuration</Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
