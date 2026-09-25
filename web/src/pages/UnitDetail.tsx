import { Link, useParams } from 'react-router-dom';
import { MapPin } from 'lucide-react';
import { extractError } from '../api/client';
import { useAlerts, useUnit, useUnitHistory } from '../api/hooks';
import { Badge, EmptyState, ErrorState, SkeletonRows } from '../components/ui';

export default function UnitDetail() {
  const { unitId } = useParams();
  const unit = useUnit(unitId);
  /* FIX (spec 4.4): history timeline from GET /units/{id}/history. */
  const history = useUnitHistory(unitId);
  const alerts = useAlerts(unitId ? { target_id: unitId } : {});

  if (unit.isLoading) return <SkeletonRows />;
  if (unit.isError) return <ErrorState message={extractError(unit.error)} onRetry={() => unit.refetch()} />;
  if (!unit.data) return <EmptyState title="Unit not found" />;
  const u = unit.data;
  const openAlert = (alerts.data ?? []).find((a) => a.status === 'open');

  return (
    <div className="space-y-4">
      <h1 className="font-mono text-xl font-bold">{u.id}</h1>

      {u.current_state === 'FLAGGED' && (
        <div className="rounded-xl border border-red-300 bg-red-50 p-4">
          <p className="font-semibold text-red-800">This unit is flagged</p>
          <p className="text-sm text-red-700">
            {openAlert ? `${openAlert.reason.replaceAll('_', ' ')} — ${openAlert.detail ?? ''}` : 'See alerts for details.'}
          </p>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <p className="text-xs text-slate-500">Current state</p>
          <Badge value={u.current_state} />
        </div>
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <p className="text-xs text-slate-500">Batch</p>
          <p className="font-mono text-sm">{u.batch_id}</p>
        </div>
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <p className="text-xs text-slate-500">Current holder</p>
          <p className="font-mono text-sm">{u.holder_org_id ?? '—'}</p>
        </div>
      </div>

      <div className="rounded-xl bg-white p-4 shadow-sm">
        <h2 className="mb-3 font-semibold">Event history</h2>
        {history.isLoading ? (
          <SkeletonRows rows={3} />
        ) : history.isError ? (
          <ErrorState message={extractError(history.error)} onRetry={() => history.refetch()} />
        ) : (history.data ?? []).length === 0 ? (
          <EmptyState title="No custody events yet" hint="This unit has been issued but not yet scanned in the field." />
        ) : (
          <ol className="relative space-y-4 border-l-2 border-slate-200 pl-5">
            {(history.data ?? []).map((e) => (
              <li key={e.id}>
                <div className="absolute -left-[7px] mt-1 h-3 w-3 rounded-full bg-brand-600" />
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{e.event_type}</span>
                  {e.resulting_state && <Badge value={e.resulting_state} />}
                  <span className="text-xs text-slate-500">{new Date(e.created_at).toLocaleString()}</span>
                </div>
                <div className="text-xs text-slate-500">
                  actor <span className="font-mono">{e.actor_org_id ?? 'system'}</span>
                  {e.gps_lat != null && e.gps_lng != null && (
                    <Link
                      to={`/dashboard/map?lat=${e.gps_lat}&lng=${e.gps_lng}`}
                      className="ml-2 inline-flex items-center gap-1 text-brand-600 hover:underline"
                    >
                      <MapPin size={12} /> {e.gps_lat.toFixed(4)}, {e.gps_lng.toFixed(4)} · View on Map
                    </Link>
                  )}
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
