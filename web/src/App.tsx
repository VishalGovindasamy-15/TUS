import { Navigate, Route, Routes } from 'react-router-dom';
import { RequireAdmin, RequireAuth, RequireOrg, RootRedirect } from './components/guards';
import { DashboardLayout } from './components/DashboardLayout';
import { AdminLayout } from './components/AdminLayout';
import Login from './pages/Login';
import Onboarding from './pages/Onboarding';
import DashboardHome from './pages/DashboardHome';
import Batches from './pages/Batches';
import UnitDetail from './pages/UnitDetail';
import Network from './pages/Network';
import Alerts from './pages/Alerts';
import LiveMap from './pages/LiveMap';
import Team from './pages/Team';
import Settings from './pages/Settings';
import Kyc from './pages/Kyc';
import SocialListings from './pages/SocialListings';
import Containers from './pages/Containers';
import EventsLog from './pages/EventsLog';
import Profile from './pages/Profile';
import OrgApprovals from './pages/admin/OrgApprovals';
import FraudPatterns from './pages/admin/FraudPatterns';
import RegulatorAccess from './pages/admin/RegulatorAccess';
import AllAlerts from './pages/admin/AllAlerts';
import PublicVerify from './pages/PublicVerify';

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/v/:unitId" element={<PublicVerify />} />
      <Route path="/verify/:unitId" element={<PublicVerify />} />

      <Route element={<RequireAuth />}>
        <Route path="/onboarding" element={<Onboarding />} />
        <Route element={<RequireOrg />}>
          <Route path="/dashboard" element={<DashboardLayout />}>
            <Route index element={<DashboardHome />} />
            <Route path="batches" element={<Batches />} />
            <Route path="units/:unitId" element={<UnitDetail />} />
            <Route path="network" element={<Network />} />
            <Route path="alerts" element={<Alerts />} />
            <Route path="map" element={<LiveMap />} />
            <Route path="users" element={<Team />} />
            <Route path="settings" element={<Settings />} />
            <Route path="kyc" element={<Kyc />} />
            <Route path="social-listings" element={<SocialListings />} />
            <Route path="containers" element={<Containers />} />
            <Route path="events" element={<EventsLog />} />
            <Route path="profile" element={<Profile />} />
          </Route>
        </Route>
        <Route element={<RequireAdmin />}>
          <Route path="/admin" element={<AdminLayout />}>
            <Route index element={<Navigate to="/admin/orgs" replace />} />
            <Route path="orgs" element={<OrgApprovals />} />
            <Route path="alerts" element={<AllAlerts />} />
            <Route path="fraud" element={<FraudPatterns />} />
            <Route path="regulator" element={<RegulatorAccess />} />
          </Route>
        </Route>
      </Route>

      <Route path="/" element={<RootRedirect />} />
      <Route path="*" element={<div className="p-8 text-sm text-slate-500">Page not found.</div>} />
    </Routes>
  );
}
