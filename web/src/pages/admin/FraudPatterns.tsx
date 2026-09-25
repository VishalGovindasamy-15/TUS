import { extractError } from '../../api/client';
import { useFraudPatterns } from '../../api/hooks';
import { EmptyState, ErrorState, SkeletonRows } from '../../components/ui';

export default function FraudPatterns() {
  const fraud = useFraudPatterns();
  const maxReason = Math.max(1, ...(fraud.data?.top_flag_reasons.map((r) => r.count) ?? [0]));

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Fraud Patterns</h1>
      {fraud.isLoading ? (
        <SkeletonRows />
      ) : fraud.isError ? (
        <ErrorState message={extractError(fraud.error)} onRetry={() => fraud.refetch()} />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl bg-white p-4 shadow-sm">
            <h2 className="mb-3 font-semibold">Top flag reasons</h2>
            {(fraud.data?.top_flag_reasons ?? []).length === 0 ? (
              <EmptyState title="No flags recorded" />
            ) : (
              <div className="space-y-2">
                {(fraud.data?.top_flag_reasons ?? []).map((r) => (
                  <div key={r.reason} className="text-sm">
                    <div className="flex justify-between">
                      <span>{r.reason.replaceAll('_', ' ')}</span>
                      <span className="font-medium">{r.count}</span>
                    </div>
                    <div className="h-2.5 rounded-full bg-slate-100">
                      <div
                        className="h-2.5 rounded-full bg-red-500"
                        style={{ width: `${(r.count / maxReason) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="space-y-4">
            <div className="rounded-xl bg-white p-4 shadow-sm">
              <h2 className="mb-3 font-semibold">By severity</h2>
              <div className="space-y-1.5 text-sm">
                {(fraud.data?.by_severity ?? []).map((s) => (
                  <div key={s.severity} className="flex justify-between border-b border-slate-50 pb-1.5 last:border-0">
                    <span className="capitalize">{s.severity}</span>
                    <span className="font-medium">{s.count}</span>
                  </div>
                ))}
                {(fraud.data?.by_severity ?? []).length === 0 && (
                  <p className="text-sm text-slate-500">No data.</p>
                )}
              </div>
            </div>
            <div className="rounded-xl bg-white p-4 shadow-sm">
              <h2 className="mb-3 font-semibold">Last 14 days</h2>
              <div className="space-y-1.5 text-sm">
                {(fraud.data?.by_day ?? []).map((d) => (
                  <div key={d.day} className="flex justify-between border-b border-slate-50 pb-1.5 last:border-0">
                    <span className="font-mono text-xs">{d.day}</span>
                    <span className="font-medium">{d.count}</span>
                  </div>
                ))}
                {(fraud.data?.by_day ?? []).length === 0 && (
                  <p className="text-sm text-slate-500">No data.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
