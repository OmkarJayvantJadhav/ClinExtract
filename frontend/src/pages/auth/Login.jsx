import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { HeartPulse, Eye, EyeOff, ShieldCheck, LogIn } from 'lucide-react';
import { useDemoInfo, DEMO_ROLE_DESCRIPTIONS } from '@/lib/demo';

export function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const { login, isLoading, sessionEnded } = useAuth();
  const navigate = useNavigate();
  const { data: demo } = useDemoInfo();

  const signIn = async (credentials) => {
    setError('');
    try {
      await login(credentials);
      navigate('/dashboard');
    } catch (err) {
      setError(err?.message === 'Failed to fetch' ? 'Cannot reach the server. Please try again.' : (err?.message || 'Invalid username or password.'));
    }
  };

  const handleLogin = (e) => {
    e.preventDefault();
    signIn({ username, password });
  };

  return (
    <div className="flex min-h-screen">
      {/* Left Branding Panel */}
      <div className="hidden w-1/2 flex-col justify-between bg-primary p-12 text-primary-foreground lg:flex">
        <div className="flex items-center gap-2 font-bold text-2xl">
          <HeartPulse className="h-8 w-8" />
          ClinExtract
        </div>
        <div>
          <h1 className="text-4xl font-semibold tracking-tight mb-4">Intelligent Clinical Document Processing</h1>
          <p className="text-primary-foreground/80 text-lg max-w-md">
            Secure, verifiable extraction and validation platform for modern healthcare workflows.
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-primary-foreground/60">
          <ShieldCheck className="h-4 w-4" />
          HIPAA compliance disabled for this prototype instance.
        </div>
      </div>

      {/* Right Login Panel */}
      <div className="flex w-full flex-col justify-center px-4 lg:w-1/2 sm:px-12 items-center bg-muted/20">
        <div className="w-full max-w-md space-y-8">
          <div className="flex flex-col items-center gap-2 lg:hidden mb-8">
            <HeartPulse className="h-10 w-10 text-primary" />
            <span className="text-2xl font-bold">ClinExtract</span>
          </div>

          {demo?.enabled && (
            <Card className="border-primary/30 bg-primary/5">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">Try the live demo</CardTitle>
                <CardDescription>
                  Shared accounts with synthetic data only. Sign in as an operator to upload a sample report,
                  then as a reviewer to check it.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-2">
                {demo.accounts.map(account => (
                  <Button key={account.username} variant="outline" className="h-auto justify-start py-2 text-left bg-background"
                    disabled={isLoading} onClick={() => signIn({ username: account.username, password: demo.password })}>
                    <LogIn className="h-4 w-4 mr-3 shrink-0" />
                    <span>
                      <span className="block font-medium">Sign in as {account.username}</span>
                      <span className="block text-xs text-muted-foreground font-normal">
                        {DEMO_ROLE_DESCRIPTIONS[account.role] ?? account.role}
                      </span>
                    </span>
                  </Button>
                ))}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Sign In</CardTitle>
              <CardDescription>Enter your credentials to access the secure portal.</CardDescription>
            </CardHeader>
            <form onSubmit={handleLogin}>
              <CardContent className="space-y-4">
                {sessionEnded && !error && (
                  <div className="p-3 text-sm bg-muted border rounded-md">Your session has ended. Please sign in again.</div>
                )}
                {error && (
                  <div className="p-3 text-sm text-destructive-foreground bg-destructive/10 border border-destructive/20 rounded-md">
                    {error}
                  </div>
                )}
                <div className="space-y-2">
                  <Label htmlFor="username">Username</Label>
                  <Input 
                    id="username" 
                    type="text" 
                    required 
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <div className="relative">
                    <Input 
                      id="password" 
                      type={showPassword ? "text" : "password"} 
                      required 
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                    <Button 
                      type="button"
                      variant="ghost" 
                      size="icon" 
                      className="absolute right-0 top-0 h-full px-3 text-muted-foreground hover:text-foreground"
                      onClick={() => setShowPassword(!showPassword)}
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      <span className="sr-only">Toggle password visibility</span>
                    </Button>
                  </div>
                </div>
              </CardContent>
              <CardFooter className="flex flex-col gap-4">
                <Button className="w-full" type="submit" disabled={isLoading}>
                  {isLoading ? "Authenticating..." : "Sign In"}
                </Button>
                <div className="text-center text-xs text-muted-foreground">
                  Educational prototype using synthetic data.
                </div>
              </CardFooter>
            </form>
          </Card>
        </div>
      </div>
    </div>
  );
}
