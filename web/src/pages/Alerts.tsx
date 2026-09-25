import { useState } from 'react';
import { Link } from 'react-router-dom';
import { extractError } from '../api/client';
import { useAlerts, useReviewAlert } from '../api/hooks';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../components/Toast';
import { Badge, EmptyState, ErrorState, Gated, SkeletonRows } from '../components/ui';

export default function Alerts() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [severity, setSeverity] = useState('');
  const [status, setStatus] = useState('');
  const params: Record<string, string> = {};
  if (severity) params.severity = severity;
  if (status) params.status = status;
  const alerts = useAlerts(params);
  const review = useReviewAlert();
  const canReview = user?.role === 'org_admin';

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Alerts</h1>
      <div className="flex gap-2">
        <select value={severity} onChange={(e) => setSeverity(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm">
          <option value="">All severities</option>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm">
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="reviewed">Reviewed</option>
        </select>
      </div>

      {alerts.isLoading ? (
        <SkeletonRows />
      ) : alerts.isError ? (
        <ErrorState message={extractError(alerts.error)} onRetry={() => alerts.refetch()} />
      ) : (alerts.data ?? []).length === 0 ? (
        <EmptyState title="No alerts" hint="Fraud and anomaly alerts for your organisation will appear here." />
      ) : (
        <div className="space-y-2">
          {(alerts.data ?? []).map((a) => (
            <div key={a.id} className="flex flex-wrap items-center gap-2 rounded-xl bg-white p-3 shadow-sm">
              <Badge value={a.severity} />
              <Badge value={a.status} />
              <span className="font-medium">{a.reason.replaceAll('_', ' ')}</span>
              <Link to={`/dashboard/units/${a.target_id}`} className="font-mono text-sm text-brand-600 hover:underline">
                {a.target_id}
              </Link>
              {a.detail && <span className="w-full text-xs text-slate-500">{a.detail}</span>}
              <span className="ml-auto text-xs text-slate-400">{new Date(a.created_at).toLocaleString()}</span>
              {a.status === 'open' && (
                <Gated allowed={canReview} reason="Only org_admin can mark alerts reviewed">
                  <button
                    disabled={!canReview || review.isPending}
                    onClick={async () => {
                      try {
                        await review.mutateAsync(a.id);
                        toast('success', 'Alert marked reviewed');
                      } catch (e) {
                        toast('error', extractError(e));
                      }
                    }}
                    className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs hover:bg-slate-50 disabled:opacity-50"
                  >
                    Mark reviewed
                  </button>
                </Gated>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
