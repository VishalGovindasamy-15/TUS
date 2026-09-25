import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { Bell, Building2, LogOut, ShieldAlert, KeyRound } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';

const ITEMS = [
  { path: '/admin/orgs', label: 'Org Approvals', icon: <Building2 size={17} /> },
  { path: '/admin/alerts', label: 'All Alerts', icon: <Bell size={17} /> },
  { path: '/admin/fraud', label: 'Fraud Patterns', icon: <ShieldAlert size={17} /> },
  { path: '/admin/regulator', label: 'Regulator Access', icon: <KeyRound size={17} /> },
];

export function AdminLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const onLogout = async () => {
    await logout();
    navigate('/login');
  };
  return (
    <div className="flex min-h-screen">
      <aside className="flex w-60 shrink-0 flex-col bg-slate-900 text-slate-200">
        <div className="px-5 py-4 text-lg font-bold tracking-wide text-white">TrustUs · Admin</div>
        <nav className="flex-1 space-y-1 px-3">
          {ITEMS.map((item) => (
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
        </nav>
        <div className="border-t border-slate-700 p-3 text-xs">
          <div className="truncate px-2 text-slate-400">{user?.phone} · platform admin</div>
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
