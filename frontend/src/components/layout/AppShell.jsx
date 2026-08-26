import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';

export function AppShell() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const toggleSidebar = () => {
    // Only applies to desktop collapse state for now
    setSidebarCollapsed(!sidebarCollapsed);
  };

  const toggleMobileMenu = () => {
    setMobileMenuOpen(!mobileMenuOpen);
  };

  return (
    <div className="flex min-h-screen w-full flex-col bg-muted/20 md:flex-row">
      {/* Sidebar for Desktop */}
      <Sidebar collapsed={sidebarCollapsed} />
      
      <div className="flex flex-col sm:gap-4 sm:py-4 w-full md:flex-1">
        <Header toggleSidebar={toggleMobileMenu} />
        
        <main className="flex-1 items-start p-4 sm:px-6 sm:py-0 md:gap-8">
          {/* Main content routes render here */}
          <Outlet />
        </main>
      </div>
    </div>
  );
}
