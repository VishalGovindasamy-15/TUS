import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, extractError } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../components/Toast';
import { Field, inputCls } from '../components/ui';

export default function Login() {
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [code, setCode] = useState('');
  const [step, setStep] = useState<'phone' | 'otp'>('phone');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const { login, mfaChallenge } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();

  const requestOtp = async () => {
    setBusy(true);
    setError('');
    try {
      await api.post('/auth/otp/request', { phone });
      setStep('otp');
      toast('success', 'OTP sent');
    } catch (e) {
      setError(extractError(e));
    } finally {
      setBusy(false);
    }
  };

  const verify = async () => {
    setBusy(true);
    setError('');
    try {
      const res = await login(phone, otp);
      if (res.mfa) {
        setMfaToken(res.mfaToken!);
      } else {
        // RootRedirect routes by role/org after auth state settles
        navigate('/', { replace: true });
      }
    } catch (e) {
      setError(extractError(e));
    } finally {
      setBusy(false);
    }
  };

  const challenge = async () => {
    setBusy(true);
    setError('');
    try {
      await mfaChallenge(mfaToken!, code);
      navigate('/', { replace: true });
    } catch (e) {
      setError(extractError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow">
        <h1 className="mb-1 text-xl font-bold">TrustUs</h1>
        <p className="mb-5 text-sm text-slate-500">Sign in with your phone number</p>
        {mfaToken ? (
          <div className="space-y-3">
            <Field label="Authenticator code">
              <input className={inputCls} value={code} onChange={(e) => setCode(e.target.value)} placeholder="6-digit code" />
            </Field>
            <button onClick={challenge} disabled={busy} className="w-full rounded-lg bg-brand-600 py-2 text-sm text-white hover:bg-brand-700 disabled:opacity-50">
              {busy ? 'Verifying…' : 'Verify'}
            </button>
          </div>
        ) : step === 'phone' ? (
          <div className="space-y-3">
            <Field label="Phone">
              <input className={inputCls} value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+91…" />
            </Field>
            <button onClick={requestOtp} disabled={busy || !phone} className="w-full rounded-lg bg-brand-600 py-2 text-sm text-white hover:bg-brand-700 disabled:opacity-50">
              {busy ? 'Sending…' : 'Send OTP'}
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <Field label={`OTP sent to ${phone}`}>
              <input className={inputCls} value={otp} onChange={(e) => setOtp(e.target.value)} placeholder="6-digit OTP" />
            </Field>
            <button onClick={verify} disabled={busy || !otp} className="w-full rounded-lg bg-brand-600 py-2 text-sm text-white hover:bg-brand-700 disabled:opacity-50">
              {busy ? 'Verifying…' : 'Verify & sign in'}
            </button>
            <button onClick={() => setStep('phone')} className="w-full text-xs text-slate-500 hover:underline">
              Use a different number
            </button>
          </div>
        )}
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </div>
    </div>
  );
}
