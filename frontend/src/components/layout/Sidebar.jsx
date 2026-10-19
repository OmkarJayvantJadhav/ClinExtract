import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Files, 
  ClipboardCheck, 
  Upload,
  BarChart3, 
  Activity, 
  ShieldAlert, 
  Users, 
  Settings,
  HeartPulse
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { useAuth } from '@/context/AuthContext';
import { ROUTE_ROLES } from '@/routes/roles';

const navItems = [
  { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
  { name: 'Documents', path: '/documents', icon: Files },
  { name: 'Upload', path: '/documents/upload', icon: Upload },
  { name: 'Review Queue', path: '/review', icon: ClipboardCheck },
  { name: 'Analytics', path: '/analytics', icon: BarChart3 },
  { name: 'Audit Logs', path: '/audit', icon: ShieldAlert },
  { name: 'System Health', path: '/system-health', icon: Activity },
  { name: 'Users', path: '/users', icon: Users },
  { name: 'Settings', path: '/settings', icon: Settings },
];

/**
 * Navigation. On small screens it is hidden until opened from the header's menu button, then
 * shown over the page; picking a page or tapping outside closes it (`onClose`).
 */
export function Sidebar({ collapsed, mobileOpen = false, onClose = () => {} }) {
  const { hasRole } = useAuth();
  const visibleItems = navItems.filter(item => !ROUTE_ROLES[item.path] || hasRole(ROUTE_ROLES[item.path]));

  return (
    <>
    {mobileOpen && <div className="fixed inset-0 z-30 bg-black/40 md:hidden" onClick={onClose} aria-hidden="true" />}
    <aside className={cn(
      "fixed inset-y-0 left-0 z-40 flex flex-col border-r bg-sidebar text-sidebar-foreground transition-all duration-300 md:static",
      collapsed && !mobileOpen ? "w-16" : "w-64",
      !mobileOpen && "max-md:hidden"
    )}>
      <div className="flex h-16 items-center border-b border-sidebar-border px-4 py-4">
        <div className="flex items-center gap-2 font-semibold">
          <HeartPulse className="h-6 w-6 text-sidebar-primary" />
          {!collapsed && <span className="text-lg tracking-tight">ClinExtract</span>}
        </div>
      </div>
      <div className="flex-1 overflow-auto py-4">
        <nav className="grid items-start px-2 text-sm font-medium">
          <TooltipProvider delayDuration={0}>
            {visibleItems.map((item) => (
              <Tooltip key={item.path} disableHoverableContent>
                <TooltipTrigger asChild>
                  <NavLink
                    to={item.path}
                    onClick={onClose}
                    end={item.path === '/documents'}
                    className={({ isActive }) => cn(
                      "flex items-center gap-3 rounded-md px-3 py-2 transition-colors",
                      isActive 
                        ? "bg-sidebar-accent text-sidebar-accent-foreground" 
                        : "text-sidebar-foreground/80 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground",
                      collapsed && "justify-center px-0"
                    )}
                  >
                    <item.icon className={cn("h-5 w-5", collapsed && "mx-auto")} />
                    {!collapsed && <span>{item.name}</span>}
                  </NavLink>
                </TooltipTrigger>
                {collapsed && (
                  <TooltipContent side="right" className="ml-2">
                    {item.name}
                  </TooltipContent>
                )}
              </Tooltip>
            ))}
          </TooltipProvider>
        </nav>
      </div>
    </aside>
    </>
  );
}
