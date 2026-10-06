import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, UserPlus, KeyRound, Unlock, LogOut, Lock } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ErrorState, EmptyState } from '@/components/common/FeedbackStates';
import { fetchApi } from '@/services/apiClient';
import { useAuth } from '@/context/AuthContext';

const ROLES = ['ADMIN', 'REVIEWER', 'OPERATOR', 'VIEWER'];

function isLocked(user) {
  return user.locked_until && new Date(user.locked_until) > new Date();
}

function CreateUserDialog({ open, onOpenChange }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ username: '', role: 'VIEWER', password: '' });
  const mutation = useMutation({
    mutationFn: () => fetchApi('/users', { method: 'POST', body: JSON.stringify(form) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      onOpenChange(false);
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create user</DialogTitle>
          <DialogDescription>Share the initial password securely; the user can change it in Settings.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-2">
          <div className="grid gap-2">
            <Label htmlFor="new-username">Username</Label>
            <Input id="new-username" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} autoComplete="off" />
          </div>
          <div className="grid gap-2">
            <Label>Role</Label>
            <Select value={form.role} onValueChange={role => setForm({ ...form, role })}>
              <SelectTrigger aria-label="Role"><SelectValue /></SelectTrigger>
              <SelectContent>{ROLES.map(r => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="new-password">Initial password</Label>
            <Input id="new-password" type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} autoComplete="new-password" />
            <p className="text-xs text-muted-foreground">At least 12 characters, mixing three of: lowercase, uppercase, digits, symbols.</p>
          </div>
          {mutation.isError && <p className="text-sm text-destructive">{mutation.error.message}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={() => mutation.mutate()} disabled={!form.username || !form.password || mutation.isPending}>Create</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ResetPasswordDialog({ user, onOpenChange }) {
  const queryClient = useQueryClient();
  const [password, setPassword] = useState('');
  const mutation = useMutation({
    mutationFn: () => fetchApi(`/users/${user.id}/reset-password`, { method: 'POST', body: JSON.stringify({ new_password: password }) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      onOpenChange(false);
    },
  });
  return (
    <Dialog open={Boolean(user)} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Reset password for {user?.username}</DialogTitle>
          <DialogDescription>Their existing sessions are signed out and any lockout is cleared.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-2 py-2">
          <Label htmlFor="reset-password">New password</Label>
          <Input id="reset-password" type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="new-password" />
          {mutation.isError && <p className="text-sm text-destructive">{mutation.error.message}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={() => mutation.mutate()} disabled={!password || mutation.isPending}>Reset password</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function UserManagement() {
  const { user: me } = useAuth();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [resetUser, setResetUser] = useState(null);
  const [actionError, setActionError] = useState('');

  const { data: users, isLoading, error, refetch } = useQuery({
    queryKey: ['users'],
    queryFn: () => fetchApi('/users'),
  });

  const action = useMutation({
    mutationFn: ({ path, method = 'POST', body }) => fetchApi(path, { method, body: body ? JSON.stringify(body) : undefined }),
    onSuccess: () => {
      setActionError('');
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
    onError: (err) => setActionError(err.message),
  });

  return (
    <div className="flex flex-col gap-6 w-full h-full">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">User Management</h1>
          <p className="text-muted-foreground">Accounts, roles and access.</p>
        </div>
        <Button onClick={() => setCreateOpen(true)}><UserPlus className="h-4 w-4 mr-2" /> Add User</Button>
      </div>

      {actionError && <div className="rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{actionError}</div>}

      <Card className="flex-1 flex flex-col">
        <CardContent className="p-0 flex-1 overflow-auto">
          {isLoading ? (
            <div className="flex h-40 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
          ) : error ? (
            <ErrorState message={error.message} onRetry={refetch} />
          ) : !users?.length ? (
            <EmptyState title="No users" message="No user accounts exist yet." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Username</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Password changed</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((u) => {
                  const self = u.id === me?.id;
                  return (
                    <TableRow key={u.id}>
                      <TableCell className="font-medium">{u.username}{self && <span className="ml-2 text-xs text-muted-foreground">(you)</span>}</TableCell>
                      <TableCell>
                        <Select value={u.role} disabled={self || action.isPending}
                          onValueChange={role => action.mutate({ path: `/users/${u.id}`, method: 'PATCH', body: { role } })}>
                          <SelectTrigger className="h-8 w-[130px]" aria-label={`Role for ${u.username}`}><SelectValue /></SelectTrigger>
                          <SelectContent>{ROLES.map(r => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell>
                        {isLocked(u) ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-warning/20 px-2 py-0.5 text-xs font-medium text-warning-foreground"><Lock className="h-3 w-3" /> Locked</span>
                        ) : (
                          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${u.is_active ? 'bg-success/10 text-success' : 'bg-muted text-muted-foreground'}`}>
                            {u.is_active ? 'Active' : 'Inactive'}
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">{u.password_changed_at ? new Date(u.password_changed_at).toLocaleDateString() : '—'}</TableCell>
                      <TableCell className="text-right whitespace-nowrap">
                        {isLocked(u) && (
                          <Button variant="ghost" size="sm" onClick={() => action.mutate({ path: `/users/${u.id}/unlock` })}><Unlock className="h-4 w-4 mr-1" /> Unlock</Button>
                        )}
                        <Button variant="ghost" size="sm" onClick={() => setResetUser(u)}><KeyRound className="h-4 w-4 mr-1" /> Reset password</Button>
                        {!self && (
                          <>
                            <Button variant="ghost" size="sm" onClick={() => action.mutate({ path: `/users/${u.id}/revoke-sessions` })}><LogOut className="h-4 w-4 mr-1" /> Sign out</Button>
                            <Button variant="ghost" size="sm" className={u.is_active ? 'text-destructive' : ''}
                              onClick={() => action.mutate({ path: `/users/${u.id}`, method: 'PATCH', body: { is_active: !u.is_active } })}>
                              {u.is_active ? 'Deactivate' : 'Activate'}
                            </Button>
                          </>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <CreateUserDialog key={createOpen ? 'open' : 'closed'} open={createOpen} onOpenChange={setCreateOpen} />
      <ResetPasswordDialog key={resetUser?.id || 'none'} user={resetUser} onOpenChange={(open) => { if (!open) setResetUser(null); }} />
    </div>
  );
}
