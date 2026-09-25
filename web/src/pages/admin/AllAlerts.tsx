import { useState } from 'react';
import { extractError } from '../../api/client';
import { useAdminAlerts, useReviewAlert } from '../../api/hooks';
import { useToast } from '../../components/Toast';
import { Badge, EmptyState, ErrorState, SkeletonRows } from '../../components/ui';

export default function AllAlerts() {
  const { toast } = useToast();
  const [severity, setSeverity] = useState('');
  const [reason, setReason] = useState('');
  const params: Record<string, string> = {};
  if (severity) params.severity = severity;
  if (reason) params.reason = reason;
  const alerts = useAdminAlerts(params);
  const review = useReviewAlert();

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">All Alerts</h1>
      <div className="flex gap-2">
        <select value={severity} onChange={(e) => setSeverity(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm">
          <option value="">All severities</option>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
        </select>
        <select value={reason} onChange={(e) => setReason(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm">
          <option value="">All reasons</option>
          <option value="impossible_travel">Impossible travel</option>
          <option value="unauthorized_route">Unauthorized route</option>
          <option value="excessive_scan_freq">Excessive scan frequency</option>
          <option value="multi_location_verify">Multi-location verify</option>
        </select>
      </div>
      {alerts.isLoading ? (
        <SkeletonRows />
      ) : alerts.isError ? (
        <ErrorState message={extractError(alerts.error)} onRetry={() => alerts.refetch()} />
      ) : (alerts.data ?? []).length === 0 ? (
        <EmptyState title="No alerts" />
      ) : (
        <div className="space-y-2">
          {(alerts.data ?? []).map((a) => (
            <div key={a.id} className="flex flex-wrap items-center gap-2 rounded-xl bg-white p-3 shadow-sm">
              <Badge value={a.severity} />
              <Badge value={a.status} />
              <span className="font-medium">{a.reason.replaceAll('_', ' ')}</span>
              <span className="font-mono text-sm">{a.target_id}</span>
              <span className="font-mono text-xs text-slate-400">org {a.org_id.slice(0, 12)}…</span>
              {a.detail && <span className="w-full text-xs text-slate-500">{a.detail}</span>}
              <span className="ml-auto text-xs text-slate-400">{new Date(a.created_at).toLocaleString()}</span>
              {a.status === 'open' && (
                <button
                  disabled={review.isPending}
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
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
