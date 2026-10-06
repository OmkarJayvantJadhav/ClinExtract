import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAuth } from '@/context/AuthContext';

// Mirrors backend/src/validation (engine auto_accept_threshold and categorize_confidence).
const THRESHOLDS = [
  { label: 'Auto-accept threshold', value: '90%', help: 'Documents whose overall confidence is at or above this value, with every field valid, are accepted without review.' },
  { label: 'Review recommended below', value: '90%', help: 'Fields below this confidence are flagged "review recommended".' },
  { label: 'Low confidence below', value: '70%', help: 'Fields below this confidence always route the document to human review.' },
];

function ReadOnlyRow({ label, value, help }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b py-3 last:border-0">
      <div>
        <p className="text-sm font-medium">{label}</p>
        {help && <p className="text-xs text-muted-foreground">{help}</p>}
      </div>
      <span className="font-mono text-sm">{value}</span>
    </div>
  );
}

export function Settings() {
  const { user } = useAuth();

  return (
    <div className="flex flex-col gap-6 max-w-4xl mx-auto w-full">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">Your profile and the system's current configuration.</p>
      </div>

      <Tabs defaultValue="profile" className="w-full">
        <TabsList className="grid w-full grid-cols-2 md:w-[400px]">
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="confidence">Confidence Thresholds</TabsTrigger>
        </TabsList>

        <TabsContent value="profile" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Profile Details</CardTitle>
              <CardDescription>Your account as known to ClinExtract.</CardDescription>
            </CardHeader>
            <CardContent>
              <ReadOnlyRow label="Username" value={user?.username ?? '—'} />
              <ReadOnlyRow label="Role" value={user?.role ?? '—'} />
              <ReadOnlyRow label="Member since" value={user?.created_at ? new Date(user.created_at).toLocaleDateString() : '—'} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="confidence" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Global Confidence Thresholds</CardTitle>
              <CardDescription>
                Current routing behaviour (read-only; configured in the backend validation engine).
                <span className="block mt-2 font-medium text-destructive">These thresholds control workflow routing and are not clinical safety thresholds.</span>
              </CardDescription>
            </CardHeader>
            <CardContent>
              {THRESHOLDS.map(t => <ReadOnlyRow key={t.label} {...t} />)}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
