import React from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  Bell, Boxes, FileUp, History, LogOut, Map as MapIcon, Network,
  Package, Settings, Share2, User as UserIcon, Users,
} from 'lucide-react';
import { useAuth } from '../auth/AuthContext';

interface NavItem { path: string; label: string; icon: React.ReactNode }

/* Complete coverage for all 7 org types (spec section 2). */
export const ALL_NAV: Record<string, NavItem[]> = {
  manufacturer: [
    { path: '/dashboard/batches', label: 'Batches & Units', icon: <Package size={17} /> },
    { path: '/dashboard/network', label: 'Network', icon: <Network size={17} /> },
    { path: '/dashboard/alerts', label: 'Alerts', icon: <Bell size={17} /> },
    { path: '/dashboard/map', label: 'Live Map', icon: <MapIcon size={17} /> },
    { path: '/dashboard/users', label: 'Team', icon: <Users size={17} /> },
    { path: '/dashboard/settings', label: 'Settings', icon: <Settings size={17} /> },
  ],
  regional_agent: [
    { path: '/dashboard/network', label: 'Network', icon: <Network size={17} /> },
    { path: '/dashboard/alerts', label: 'Alerts', icon: <Bell size={17} /> },
    { path: '/dashboard/map', label: 'Live Map', icon: <MapIcon size={17} /> },
    { path: '/dashboard/users', label: 'Team', icon: <Users size={17} /> },
    { path: '/dashboard/settings', label: 'Settings', icon: <Settings size={17} /> },
  ],
  distributor_authorized: [
    { path: '/dashboard/containers', label: 'Containers', icon: <Boxes size={17} /> },
    { path: '/dashboard/network', label: 'Network', icon: <Network size={17} /> },
    { path: '/dashboard/alerts', label: 'Alerts', icon: <Bell size={17} /> },
    { path: '/dashboard/map', label: 'Live Map', icon: <MapIcon size={17} /> },
    { path: '/dashboard/users', label: 'Team', icon: <Users size={17} /> },
    { path: '/dashboard/settings', label: 'Settings', icon: <Settings size={17} /> },
  ],
  distributor_sub: [
    { path: '/dashboard/alerts', label: 'Alerts', icon: <Bell size={17} /> },
    { path: '/dashboard/map', label: 'Live Map', icon: <MapIcon size={17} /> },
    { path: '/dashboard/users', label: 'Team', icon: <Users size={17} /> },
    { path: '/dashboard/settings', label: 'Settings', icon: <Settings size={17} /> },
  ],
  retailer: [
    { path: '/dashboard/alerts', label: 'Alerts', icon: <Bell size={17} /> },
    { path: '/dashboard/map', label: 'Live Map', icon: <MapIcon size={17} /> },
    { path: '/dashboard/users', label: 'Team', icon: <Users size={17} /> },
    { path: '/dashboard/settings', label: 'Settings', icon: <Settings size={17} /> },
  ],
  transporter: [
    { path: '/dashboard/alerts', label: 'Alerts', icon: <Bell size={17} /> },
    { path: '/dashboard/users', label: 'Team', icon: <Users size={17} /> },
    { path: '/dashboard/settings', label: 'Settings', icon: <Settings size={17} /> },
  ],
  social_seller: [
    { path: '/dashboard/social-listings', label: 'Social Listings', icon: <Share2 size={17} /> },
    { path: '/dashboard/alerts', label: 'Alerts', icon: <Bell size={17} /> },
    { path: '/dashboard/users', label: 'Team', icon: <Users size={17} /> },
    { path: '/dashboard/settings', label: 'Settings', icon: <Settings size={17} /> },
  ],
};

export function defaultPathFor(orgType: string): string {
  return ALL_NAV[orgType]?.[0]?.path ?? '/dashboard/alerts';
}

export function DashboardLayout() {
  const { user, org, logout } = useAuth();
  const navigate = useNavigate();
  const items = ALL_NAV[org?.org_type ?? ''] ?? [];

  const onLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-60 shrink-0 flex-col bg-slate-900 text-slate-200">
        <div className="px-5 py-4 text-lg font-bold tracking-wide text-white">TrustUs</div>
        <div className="px-5 pb-3 text-xs text-slate-400">
          <div className="truncate font-medium text-slate-200">{org?.name}</div>
          <div className="capitalize">{org?.org_type.replaceAll('_', ' ')}</div>
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {items.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm ${
                  isActive ? 'bg-slate-700 text-white' : 'hover:bg-slate-800'
                }`
              }
            >
              {item.icon}
              {item.label}
            </NavLink>
          ))}
          {org?.approval_status === 'pending' && (
            <NavLink
              to="/dashboard/kyc"
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm ${
                  isActive ? 'bg-slate-700 text-white' : 'hover:bg-slate-800'
                }`
              }
            >
              <FileUp size={17} /> KYC Upload
            </NavLink>
          )}
          <NavLink
            to="/dashboard/profile"
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm ${
                isActive ? 'bg-slate-700 text-white' : 'hover:bg-slate-800'
              }`
            }
          >
            <UserIcon size={17} /> My Profile
          </NavLink>
          <NavLink
            to="/dashboard/events"
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-slate-400 ${
                isActive ? 'bg-slate-700 text-white' : 'hover:bg-slate-800'
              }`
            }
          >
            <History size={17} /> Events Log
          </NavLink>
        </nav>
        <div className="border-t border-slate-700 p-3 text-xs">
          <div className="truncate px-2 text-slate-400">{user?.phone} · {user?.role}</div>
          <button
            onClick={onLogout}
            className="mt-1 flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-slate-300 hover:bg-slate-800"
          >
            <LogOut size={15} /> Logout
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}
