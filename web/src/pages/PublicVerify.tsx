import { useParams } from 'react-router-dom';
import { CheckCircle2, Clock, ShieldAlert, XOctagon } from 'lucide-react';
import { extractError } from '../api/client';
import { useVerify } from '../api/hooks';
import { EmptyState, ErrorState, SkeletonRows } from '../components/ui';

const STATE_UI = {
  genuine: { icon: <CheckCircle2 size={40} className="text-emerald-600" />, title: 'Genuine product', cls: 'text-emerald-700' },
  not_yet_in_circulation: { icon: <Clock size={40} className="text-slate-500" />, title: 'Not yet in circulation', cls: 'text-slate-600' },
  flagged: { icon: <ShieldAlert size={40} className="text-red-600" />, title: 'Flagged — caution', cls: 'text-red-700' },
  recalled: { icon: <XOctagon size={40} className="text-orange-600" />, title: 'Recalled by manufacturer', cls: 'text-orange-700' },
} as const;

export default function PublicVerify() {
  const { unitId } = useParams();
  const verify = useVerify(unitId);
  const geo = 'geolocation' in navigator;

  const verifyWithLocation = () => {
    navigator.geolocation.getCurrentPosition(
      () => verify.refetch(),
      () => verify.refetch(),
      { timeout: 5000 },
    );
  };

  return (
    <div className="mx-auto flex min-h-screen max-w-lg flex-col items-center justify-center p-4">
      <h1 className="mb-4 text-lg font-bold">TrustUs Verification</h1>
      {verify.isLoading ? (
        <div className="w-full"><SkeletonRows rows={3} /></div>
      ) : verify.isError ? (
        <div className="w-full">
          <ErrorState message={extractError(verify.error)} onRetry={() => verify.refetch()} />
        </div>
      ) : !verify.data ? (
        <EmptyState title="Invalid or unknown code" />
      ) : (
        <div className="w-full rounded-xl bg-white p-6 text-center shadow">
          <div className="flex justify-center">{STATE_UI[verify.data.status].icon}</div>
          <h2 className={`mt-2 text-xl font-bold ${STATE_UI[verify.data.status].cls}`}>
            {STATE_UI[verify.data.status].title}
          </h2>
          {verify.data.status === 'flagged' && verify.data.flag_reason && (
            <p className="mt-1 text-sm text-red-600">Reason: {verify.data.flag_reason.replaceAll('_', ' ')}</p>
          )}
          <div className="mt-4 space-y-1 text-left text-sm">
            <p><span className="text-slate-500">Product:</span> {verify.data.product_name ?? '—'} ({verify.data.product_code ?? '—'})</p>
            <p><span className="text-slate-500">Batch:</span> {verify.data.batch_number ?? '—'}</p>
            <p className="font-mono text-xs text-slate-400">{verify.data.unit_id}</p>
          </div>
          {verify.data.disclosures.length > 0 && (
            <div className="mt-4 border-t border-slate-100 pt-3 text-left">
              <h3 className="mb-2 text-sm font-semibold">Product information</h3>
              <div className="space-y-1 text-sm">
                {verify.data.disclosures.filter((d) => d.value).map((d) => (
                  <p key={d.field_key}>
                    <span className="text-slate-500">{d.label}:</span> {d.value}
                  </p>
                ))}
              </div>
            </div>
          )}
          {verify.data.last_events.length > 0 && (
            <div className="mt-4 border-t border-slate-100 pt-3 text-left">
              <h3 className="mb-2 text-sm font-semibold">Chain of custody (recent)</h3>
              <div className="space-y-1.5">
                {verify.data.last_events.map((e, i) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <span className="font-medium">{e.event_type}</span>
                    <span className="text-slate-500">{new Date(e.timestamp).toLocaleDateString()}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {geo && (
            <button onClick={verifyWithLocation} className="mt-4 text-xs text-slate-400 hover:underline">
              Re-verify with location (helps detect copied codes)
            </button>
          )}
        </div>
      )}
    </div>
  );
}
