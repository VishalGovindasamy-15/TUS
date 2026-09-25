import axios, { AxiosError, AxiosInstance, AxiosRequestConfig } from 'axios';

/** Default uses the Vite dev proxy (/api -> :8000); override per .env.example. */
const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api/v1';
export const API_BASE = BASE;

/* Access token lives in memory only — never localStorage. */
let accessToken: string | null = null;
export const setAccessToken = (t: string | null) => { accessToken = t; };
export const getAccessToken = () => accessToken;

const REFRESH_KEY = 'trustus_refresh_token';
export const getRefreshToken = () => sessionStorage.getItem(REFRESH_KEY);
export const setRefreshToken = (t: string | null) =>
  t ? sessionStorage.setItem(REFRESH_KEY, t) : sessionStorage.removeItem(REFRESH_KEY);

export const api: AxiosInstance = axios.create({ baseURL: BASE });

/* Single-flight refresh: concurrent 401s queue behind one refresh call. */
let refreshing: Promise<string | null> | null = null;
export function doRefresh(): Promise<string | null> {
  if (!refreshing) {
    const rt = getRefreshToken();
    if (!rt) return Promise.resolve(null);
    refreshing = axios
      .post(`${BASE}/auth/refresh`, { refresh_token: rt })
      .then((res) => {
        setAccessToken(res.data.access_token as string);
        setRefreshToken(res.data.refresh_token as string);
        return res.data.access_token as string;
      })
      .catch(() => {
        setAccessToken(null);
        setRefreshToken(null);
        window.dispatchEvent(new Event('trustus:logout'));
        return null;
      })
      .finally(() => { refreshing = null; });
  }
  return refreshing;
}

api.interceptors.request.use((cfg) => {
  if (accessToken) cfg.headers.Authorization = `Bearer ${accessToken}`;
  return cfg;
});

const NO_RETRY = /\/auth\/(otp|mfa)\//;
api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const cfg = error.config as (AxiosRequestConfig & { _retried?: boolean }) | undefined;
    if (
      error.response?.status === 401 && cfg && !cfg._retried &&
      !(cfg.url ?? '').match(NO_RETRY)
    ) {
      cfg._retried = true;
      const token = await doRefresh();
      if (token) {
        cfg.headers = cfg.headers ?? {};
        (cfg.headers as Record<string, string>).Authorization = `Bearer ${token}`;
        return api(cfg);
      }
    }
    return Promise.reject(error);
  },
);

export function extractError(e: unknown): string {
  if (axios.isAxiosError(e)) {
    const d = e.response?.data?.detail as unknown;
    if (typeof d === 'string') return d;
    if (d && typeof d === 'object') {
      const { message, code } = d as { message?: string; code?: string };
      return message ?? code ?? 'Request failed';
    }
    if (e.response) return `Request failed (${e.response.status})`;
    return 'Network error — is the API running?';
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

/** Proactively refresh when the access token is nearly expired (KYC upload fix). */
export async function ensureFreshToken(minTtlSec = 60): Promise<boolean> {
  if (!accessToken) return false;
  try {
    const [, payload] = accessToken.split('.');
    const exp = JSON.parse(atob(payload)).exp as number;
    if (exp - Date.now() / 1000 < minTtlSec) {
      return (await doRefresh()) !== null;
    }
    return true;
  } catch {
    return true;
  }
}
