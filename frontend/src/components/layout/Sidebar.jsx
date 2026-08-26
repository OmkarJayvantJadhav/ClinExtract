import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Files, 
  ClipboardCheck, 
  Archive, 
  BarChart3, 
  Activity, 
  ShieldAlert, 
  Users, 
  Settings,
  HeartPulse
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

const navItems = [
  { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
  { name: 'Documents', path: '/documents', icon: Files },
  { name: 'Review Queue', path: '/review', icon: ClipboardCheck },
  { name: 'Records', path: '/records', icon: Archive },
  { name: 'Analytics', path: '/analytics', icon: BarChart3 },
  { name: 'Audit Logs', path: '/audit', icon: ShieldAlert },
  { name: 'System Health', path: '/system-health', icon: Activity },
  { name: 'Users', path: '/users', icon: Users },
  { name: 'Settings', path: '/settings', icon: Settings },
];

export function Sidebar({ collapsed }) {
  return (
    <aside className={cn(
      "fixed inset-y-0 left-0 z-40 flex flex-col border-r bg-sidebar text-sidebar-foreground transition-all duration-300 md:static",
      collapsed ? "w-16" : "w-64",
      "max-md:hidden" // In a real app, this would be toggled via mobile menu state
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
            {navItems.map((item) => (
              <Tooltip key={item.path} disableHoverableContent>
                <TooltipTrigger asChild>
                  <NavLink
                    to={item.path}
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
  );
}
