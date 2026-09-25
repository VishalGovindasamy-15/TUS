import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, doRefresh, getRefreshToken, setAccessToken, setRefreshToken } from '../api/client';
import type { OrgOut, UserOut } from '../api/types';

interface AuthState {
  user: UserOut | null;
  org: OrgOut | null;
  booting: boolean;
  login: (phone: string, otp: string) => Promise<{ mfa: boolean; mfaToken?: string }>;
  mfaChallenge: (mfaToken: string, code: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshOrg: () => Promise<void>;
  setOrg: (o: OrgOut | null) => void;
  setUser: (u: UserOut | null) => void;
}

const AuthContext = createContext<AuthState | null>(null);
export const useAuth = () => useContext(AuthContext)!;

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [org, setOrg] = useState<OrgOut | null>(null);
  const [booting, setBooting] = useState(true);
  const navigate = useNavigate();

  const fetchOrg = useCallback(async () => {
    try {
      const res = await api.get('/orgs/me');
      setOrg(res.data as OrgOut);
    } catch {
      setOrg(null);
    }
  }, []);

  const hardLogout = useCallback(() => {
    setAccessToken(null);
    setRefreshToken(null);
    setUser(null);
    setOrg(null);
    navigate('/login', { replace: true });
  }, [navigate]);

  useEffect(() => {
    const boot = async () => {
      if (getRefreshToken()) {
        const token = await doRefresh();
        if (token) {
          // No /auth/me endpoint: re-derive identity from a fresh refresh round-trip.
          const rt = getRefreshToken();
          if (rt) {
            try {
              const res = await api.post('/auth/refresh', { refresh_token: rt });
              setAccessToken(res.data.access_token);
              setRefreshToken(res.data.refresh_token);
              setUser(res.data.user as UserOut);
              await fetchOrg();
            } catch {
              hardLogout();
            }
          }
        }
      }
      setBooting(false);
    };
    boot();
    const onLogout = () => hardLogout();
    window.addEventListener('trustus:logout', onLogout);
    return () => window.removeEventListener('trustus:logout', onLogout);
  }, [fetchOrg, hardLogout]);

  const login = async (phone: string, otp: string) => {
    const res = await api.post('/auth/otp/verify', { phone, otp });
    if (res.data.mfa_required) {
      return { mfa: true, mfaToken: res.data.mfa_token as string };
    }
    setAccessToken(res.data.access_token);
    setRefreshToken(res.data.refresh_token);
    setUser(res.data.user as UserOut);
    await fetchOrg();
    return { mfa: false };
  };

  const mfaChallenge = async (mfaToken: string, code: string) => {
    const res = await api.post('/auth/mfa/challenge', { mfa_token: mfaToken, code });
    setAccessToken(res.data.access_token);
    setRefreshToken(res.data.refresh_token);
    setUser(res.data.user as UserOut);
    await fetchOrg();
  };

  const logout = async () => {
    try {
      await api.post('/auth/logout', { refresh_token: getRefreshToken() });
    } catch {
      /* session already dead — still clear locally */
    }
    hardLogout();
  };

  return (
    <AuthContext.Provider
      value={{ user, org, booting, login, mfaChallenge, logout, refreshOrg: fetchOrg, setOrg, setUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}
