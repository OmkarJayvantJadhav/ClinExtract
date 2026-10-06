import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/context/AuthContext';
import { fetchApi } from '@/services/apiClient';

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

function ChangePasswordCard({ minLength }) {
  const [form, setForm] = useState({ current_password: '', new_password: '', confirm: '' });
  const [done, setDone] = useState(false);
  const mutation = useMutation({
    mutationFn: () => fetchApi('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password: form.current_password, new_password: form.new_password }),
    }),
    onSuccess: () => {
      setDone(true);
      setForm({ current_password: '', new_password: '', confirm: '' });
    },
  });
  const mismatch = form.confirm && form.new_password !== form.confirm;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Change password</CardTitle>
        <CardDescription>Your other sessions are signed out when the password changes.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 max-w-md">
        <div className="grid gap-2">
          <Label htmlFor="current-password">Current password</Label>
          <Input id="current-password" type="password" autoComplete="current-password" value={form.current_password}
            onChange={e => { setDone(false); setForm({ ...form, current_password: e.target.value }); }} />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="new-password">New password</Label>
          <Input id="new-password" type="password" autoComplete="new-password" value={form.new_password}
            onChange={e => { setDone(false); setForm({ ...form, new_password: e.target.value }); }} />
          <p className="text-xs text-muted-foreground">At least {minLength ?? 12} characters, mixing three of: lowercase, uppercase, digits, symbols.</p>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="confirm-password">Confirm new password</Label>
          <Input id="confirm-password" type="password" autoComplete="new-password" value={form.confirm}
            onChange={e => setForm({ ...form, confirm: e.target.value })} />
          {mismatch && <p className="text-xs text-destructive">Passwords do not match.</p>}
        </div>
        {mutation.isError && <p className="text-sm text-destructive">{mutation.error.message}</p>}
        {done && <p className="text-sm text-success">Password changed.</p>}
        <Button className="w-fit" onClick={() => mutation.mutate()}
          disabled={!form.current_password || !form.new_password || mismatch || mutation.isPending}>
          Change password
        </Button>
      </CardContent>
    </Card>
  );
}

function ThresholdsCard({ thresholds, editable }) {
  const queryClient = useQueryClient();
  const toPct = (v) => Math.round(v * 100);
  const [form, setForm] = useState({
    auto_accept: toPct(thresholds.auto_accept),
    review_recommended: toPct(thresholds.review_recommended),
    low_confidence: toPct(thresholds.low_confidence),
  });
  const [saved, setSaved] = useState(false);
  const mutation = useMutation({
    mutationFn: () => fetchApi('/settings/confidence-thresholds', {
      method: 'PUT',
      body: JSON.stringify(Object.fromEntries(Object.entries(form).map(([k, v]) => [k, Number(v) / 100]))),
    }),
    onSuccess: () => {
      setSaved(true);
      queryClient.invalidateQueries({ queryKey: ['settings'] });
    },
  });

  const rows = [
    ['auto_accept', 'Auto-accept threshold', 'Overall confidence at or above this (with every field valid) is accepted without review.'],
    ['review_recommended', 'Review recommended below', 'Fields below this confidence are flagged "review recommended".'],
    ['low_confidence', 'Low confidence below', 'Fields below this confidence always route the document to human review.'],
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Global Confidence Thresholds</CardTitle>
        <CardDescription>
          {editable ? 'Changes apply to documents processed afterwards.' : 'Only administrators can change these.'}
          <span className="block mt-2 font-medium text-destructive">These thresholds control workflow routing and are not clinical safety thresholds.</span>
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        {rows.map(([key, label, help]) => (
          <div key={key} className="flex items-center justify-between gap-4 border-b pb-3 last:border-0">
            <div>
              <Label htmlFor={`t-${key}`} className="text-sm font-medium">{label}</Label>
              <p className="text-xs text-muted-foreground">{help}</p>
            </div>
            <div className="flex items-center gap-1">
              <Input id={`t-${key}`} type="number" min="0" max="100" className="w-[90px] text-right" disabled={!editable}
                value={form[key]} onChange={e => { setSaved(false); setForm({ ...form, [key]: e.target.value }); }} />
              <span className="text-sm text-muted-foreground">%</span>
            </div>
          </div>
        ))}
        {mutation.isError && <p className="text-sm text-destructive">{mutation.error.message}</p>}
        {saved && <p className="text-sm text-success">Thresholds saved.</p>}
        {editable && <Button className="w-fit" onClick={() => mutation.mutate()} disabled={mutation.isPending}>Save thresholds</Button>}
      </CardContent>
    </Card>
  );
}

export function Settings() {
  const { user, hasRole, logout } = useAuth();
  const navigate = useNavigate();
  const { data: settings } = useQuery({ queryKey: ['settings'], queryFn: () => fetchApi('/settings') });

  const logoutAll = useMutation({
    mutationFn: () => fetchApi('/auth/logout-all', { method: 'POST' }),
    onSuccess: async () => {
      await logout();
      navigate('/login');
    },
  });

  return (
    <div className="flex flex-col gap-6 max-w-4xl mx-auto w-full">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">Your account and the system configuration.</p>
      </div>

      <Tabs defaultValue="profile" className="w-full">
        <TabsList className="grid w-full grid-cols-3 md:w-[480px]">
          <TabsTrigger value="profile">Profile & Security</TabsTrigger>
          <TabsTrigger value="confidence">Thresholds</TabsTrigger>
          <TabsTrigger value="compliance">Data Protection</TabsTrigger>
        </TabsList>

        <TabsContent value="profile" className="mt-6 grid gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Profile</CardTitle>
            </CardHeader>
            <CardContent>
              <ReadOnlyRow label="Username" value={user?.username ?? '—'} />
              <ReadOnlyRow label="Role" value={user?.role ?? '—'} />
              <ReadOnlyRow label="Password last changed" value={user?.password_changed_at ? new Date(user.password_changed_at).toLocaleDateString() : '—'} />
            </CardContent>
          </Card>
          <ChangePasswordCard minLength={settings?.password_min_length} />
          <Card>
            <CardHeader>
              <CardTitle>Sessions</CardTitle>
              <CardDescription>Sign out of ClinExtract on every device, including this one.</CardDescription>
            </CardHeader>
            <CardContent>
              <Button variant="outline" onClick={() => logoutAll.mutate()} disabled={logoutAll.isPending}>Sign out everywhere</Button>
              {logoutAll.isError && <p className="mt-2 text-sm text-destructive">{logoutAll.error.message}</p>}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="confidence" className="mt-6">
          {settings
            ? <ThresholdsCard key={JSON.stringify(settings.confidence_thresholds)} thresholds={settings.confidence_thresholds} editable={hasRole('ADMIN')} />
            : <p className="text-sm text-muted-foreground">Loading…</p>}
        </TabsContent>

        <TabsContent value="compliance" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Data Protection</CardTitle>
              <CardDescription>Configured by the deployment (environment variables).</CardDescription>
            </CardHeader>
            <CardContent>
              <ReadOnlyRow label="Encryption at rest" value={settings ? (settings.encryption_at_rest ? 'Enabled' : 'Disabled') : '—'}
                help="Stored documents and OCR artifacts are encrypted with DOCUMENT_ENCRYPTION_KEY." />
              <ReadOnlyRow label="Automatic retention" value={settings ? (settings.document_retention_days ? `${settings.document_retention_days} days` : 'Off') : '—'}
                help="Finalized documents older than this are purged daily; audit events are kept with patient data redacted." />
              <ReadOnlyRow label="Access logging" value="Enabled" help="Document views and downloads are recorded in the audit log." />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
