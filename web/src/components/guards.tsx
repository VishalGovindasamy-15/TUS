import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

export function RequireAuth() {
  const { user, booting } = useAuth();
  const loc = useLocation();
  if (booting) return <div className="p-8 text-sm text-slate-500">Loading…</div>;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  return <Outlet />;
}

export function RequireOrg() {
  const { user, org } = useAuth();
  if (user?.role === 'platform_admin') return <Navigate to="/admin" replace />;
  if (!org) return <Navigate to="/onboarding" replace />;
  return <Outlet />;
}

export function RequireAdmin() {
  const { user } = useAuth();
  if (user?.role !== 'platform_admin') return <Navigate to="/dashboard" replace />;
  return <Outlet />;
}

export function RootRedirect() {
  const { user, org, booting } = useAuth();
  if (booting) return <div className="p-8 text-sm text-slate-500">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role === 'platform_admin') return <Navigate to="/admin" replace />;
  if (!org) return <Navigate to="/onboarding" replace />;
  return <Navigate to="/dashboard" replace />;
}
