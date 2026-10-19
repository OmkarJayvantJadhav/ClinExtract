import React from 'react';
import { useNavigate } from 'react-router-dom';
import { LogOut, User, Menu } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/context/AuthContext';

export function Header({ toggleSidebar, menuOpen = false }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const signOut = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-4 border-b bg-background px-4 sm:px-6">
      <Button variant="ghost" size="icon" className="md:hidden" onClick={toggleSidebar} aria-expanded={menuOpen}>
        <Menu className="h-5 w-5" />
        <span className="sr-only">Menu</span>
      </Button>

      <div className="flex flex-1 items-center justify-end gap-3">
        {user && (
          <div className="flex items-center gap-2 text-sm">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-secondary">
              <User className="h-4 w-4 text-secondary-foreground" />
            </span>
            <span className="hidden sm:flex sm:flex-col sm:leading-tight">
              <span className="font-medium">{user.username}</span>
              <span className="text-xs text-muted-foreground capitalize">{user.role?.toLowerCase()}</span>
            </span>
          </div>
        )}
        <Button variant="ghost" size="sm" onClick={signOut}>
          <LogOut className="h-4 w-4 sm:mr-2" />
          <span className="max-sm:sr-only">Sign out</span>
        </Button>
      </div>
    </header>
  );
}
