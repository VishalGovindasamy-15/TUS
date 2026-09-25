import { useState } from 'react';
import { api, extractError } from '../api/client';
import { useRevokeSession, useSessions } from '../api/hooks';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../components/Toast';
import { Badge, CopyButton, EmptyState, ErrorState, Field, SkeletonRows, inputCls } from '../components/ui';

export default function Profile() {
  const { user, org, logout } = useAuth();
  const { toast } = useToast();
  const sessions = useSessions();
  const revoke = useRevokeSession();
  const [enroll, setEnroll] = useState<{ secret: string; uri: string } | null>(null);
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const showMfa = user?.role === 'org_admin' || user?.role === 'platform_admin';

  const startEnroll = async () => {
    setBusy(true);
    try {
      const res = await api.post('/auth/mfa/enroll');
      setEnroll({ secret: res.data.secret, uri: res.data.otpauth_uri });
    } catch (e) {
      toast('error', extractError(e));
    } finally {
      setBusy(false);
    }
  };

  const confirmEnroll = async () => {
    setBusy(true);
    try {
      await api.post('/auth/mfa/confirm', { code });
      toast('success', 'MFA enabled');
      setEnroll(null);
      setCode('');
    } catch (e) {
      toast('error', extractError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-xl font-bold">My Profile</h1>

      <div className="rounded-xl bg-white p-4 shadow-sm">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div><p className="text-xs text-slate-500">User ID</p><p className="font-mono">{user?.id}</p></div>
          <div><p className="text-xs text-slate-500">Phone</p><p className="font-mono">{user?.phone}</p></div>
          <div><p className="text-xs text-slate-500">Role</p><p className="capitalize">{user?.role.replace('_', ' ')}</p></div>
          <div>
            <p className="text-xs text-slate-500">MFA</p>
            {user?.mfa_enabled ? <Badge value="authorized" /> : <span className="text-slate-500">Not enabled</span>}
          </div>
        </div>
      </div>

      {org && (
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <h2 className="mb-2 font-semibold">Organisation</h2>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div><p className="text-xs text-slate-500">Name</p><p>{org.name}</p></div>
            <div><p className="text-xs text-slate-500">Type</p><p className="capitalize">{org.org_type.replaceAll('_', ' ')}</p></div>
            <div><p className="text-xs text-slate-500">Status</p><Badge value={org.approval_status} /></div>
            <div><p className="text-xs text-slate-500">Categories</p><p>{org.categories.join(', ')}</p></div>
          </div>
        </div>
      )}

      {showMfa && !user?.mfa_enabled && (
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <h2 className="mb-2 font-semibold">Set up MFA (required for admins)</h2>
          {!enroll ? (
            <button onClick={startEnroll} disabled={busy} className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white disabled:opacity-50">
              {busy ? 'Starting…' : 'Start MFA setup'}
            </button>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-slate-600">
                Add this secret to your authenticator app, then enter the 6-digit code:
              </p>
              <div className="flex items-center gap-2">
                <code className="rounded bg-slate-100 px-3 py-2 font-mono text-sm">{enroll.secret}</code>
                <CopyButton text={enroll.secret} />
              </div>
              <Field label="Authenticator code">
                <input className={inputCls} value={code} onChange={(e) => setCode(e.target.value)} placeholder="123456" />
              </Field>
              <button onClick={confirmEnroll} disabled={busy || !code} className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white disabled:opacity-50">
                {busy ? 'Confirming…' : 'Enable MFA'}
              </button>
            </div>
          )}
        </div>
      )}

      <div className="rounded-xl bg-white p-4 shadow-sm">
        <h2 className="mb-2 font-semibold">Active Sessions</h2>
        {sessions.isLoading ? (
          <SkeletonRows rows={2} />
        ) : sessions.isError ? (
          <ErrorState message={extractError(sessions.error)} onRetry={() => sessions.refetch()} />
        ) : (sessions.data ?? []).filter((s) => !s.revoked_at).length === 0 ? (
          <EmptyState title="No active sessions" />
        ) : (
          <div className="space-y-2">
            {(sessions.data ?? []).filter((s) => !s.revoked_at).map((s) => (
              <div key={s.id} className="flex items-center gap-2 text-sm">
                <span>{s.device_info || 'Unknown device'}</span>
                <span className="text-xs text-slate-500">since {new Date(s.created_at).toLocaleDateString()}</span>
                <button
                  onClick={async () => {
                    try {
                      await revoke.mutateAsync(s.id);
                      toast('success', 'Session revoked');
                    } catch (e) {
                      toast('error', extractError(e));
                    }
                  }}
                  className="ml-auto rounded-lg border border-slate-300 px-2.5 py-1 text-xs hover:bg-slate-50"
                >
                  Revoke
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <button onClick={() => logout()} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm hover:bg-slate-50">
        Logout
      </button>
    </div>
  );
}
