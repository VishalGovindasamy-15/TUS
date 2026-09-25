import { Navigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { defaultPathFor } from '../components/DashboardLayout';

/* Role-aware default: land on the correct first page per org type (spec 4.1 fix). */
export default function DashboardHome() {
  const { org } = useAuth();
  return <Navigate to={defaultPathFor(org?.org_type ?? '')} replace />;
}
