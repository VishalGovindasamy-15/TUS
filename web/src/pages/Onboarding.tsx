import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, extractError } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../components/Toast';
import { Field, inputCls } from '../components/ui';
import { useAcceptInvite } from '../api/hooks';

const ORG_TYPES = [
  'manufacturer', 'regional_agent', 'distributor_authorized',
  'distributor_sub', 'retailer', 'transporter', 'social_seller',
];

export default function Onboarding() {
  const [mode, setMode] = useState<'create' | 'accept'>('create');
  const [name, setName] = useState('');
  const [orgType, setOrgType] = useState(ORG_TYPES[0]);
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const { refreshOrg } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const accept = useAcceptInvite();

  const create = async () => {
    setBusy(true);
    setError('');
    try {
      await api.post('/orgs', { name, org_type: orgType, categories: ['pharma'] });
      await refreshOrg();
      toast('success', 'Organisation created — pending approval');
      navigate('/dashboard', { replace: true });
    } catch (e) {
      setError(extractError(e));
    } finally {
      setBusy(false);
    }
  };

  const acceptInvite = async () => {
    setBusy(true);
    setError('');
    try {
      // Accepting requires an org: create a minimal one first if needed, then accept.
      try {
        await api.post('/orgs', { name: name || 'My Organisation', org_type: orgType, categories: ['pharma'] });
        await refreshOrg();
      } catch (e) {
        const msg = extractError(e);
        if (!msg.includes('already belongs')) throw e;
        await refreshOrg();
      }
      await accept.mutateAsync(code.trim());
      toast('success', 'Invite accepted');
      navigate('/dashboard', { replace: true });
    } catch (e) {
      setError(extractError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow">
        <h1 className="mb-1 text-xl font-bold">Set up your organisation</h1>
        <p className="mb-4 text-sm text-slate-500">Create a new org, or join your network with an invite code.</p>
        <div className="mb-4 flex gap-2">
          {(['create', 'accept'] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`flex-1 rounded-lg px-3 py-2 text-sm ${
                mode === m ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {m === 'create' ? 'Create org' : 'Accept invite'}
            </button>
          ))}
        </div>
        {mode === 'create' ? (
          <div className="space-y-3">
            <Field label="Organisation name">
              <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
            <Field label="Organisation type">
              <select className={inputCls} value={orgType} onChange={(e) => setOrgType(e.target.value)}>
                {ORG_TYPES.map((t) => <option key={t} value={t}>{t.replaceAll('_', ' ')}</option>)}
              </select>
            </Field>
            <button onClick={create} disabled={busy || !name} className="w-full rounded-lg bg-brand-600 py-2 text-sm text-white hover:bg-brand-700 disabled:opacity-50">
              {busy ? 'Creating…' : 'Create organisation'}
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <Field label="Organisation name (for your new org)">
              <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
            <Field label="Organisation type">
              <select className={inputCls} value={orgType} onChange={(e) => setOrgType(e.target.value)}>
                {ORG_TYPES.map((t) => <option key={t} value={t}>{t.replaceAll('_', ' ')}</option>)}
              </select>
            </Field>
            <Field label="Invite code">
              <input className={inputCls} value={code} onChange={(e) => setCode(e.target.value)} placeholder="TU-XXXXXX" />
            </Field>
            <button onClick={acceptInvite} disabled={busy || !code || !name} className="w-full rounded-lg bg-brand-600 py-2 text-sm text-white hover:bg-brand-700 disabled:opacity-50">
              {busy ? 'Accepting…' : 'Accept invite'}
            </button>
          </div>
        )}
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </div>
    </div>
  );
}
