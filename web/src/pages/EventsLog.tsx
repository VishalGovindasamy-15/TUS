import { useState } from 'react';
import { Link } from 'react-router-dom';
import { MapPin } from 'lucide-react';
import { extractError } from '../api/client';
import { useEvents } from '../api/hooks';
import { Badge, EmptyState, ErrorState, SkeletonRows } from '../components/ui';

export default function EventsLog() {
  const [targetId, setTargetId] = useState('');
  const [eventType, setEventType] = useState('');
  const [applied, setApplied] = useState<{ target_id?: string; event_type?: string }>({});
  const events = useEvents(applied);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Events Log</h1>
      <div className="flex flex-wrap gap-2">
        <input
          value={targetId}
          onChange={(e) => setTargetId(e.target.value)}
          placeholder="Target unit/container ID"
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 font-mono text-sm"
        />
        <select value={eventType} onChange={(e) => setEventType(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm">
          <option value="">All event types</option>
          {['DISPATCH', 'RECEIVE', 'SALE', 'RETURN', 'FLAG', 'UNFLAG'].map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <button
          onClick={() => setApplied({ ...(targetId ? { target_id: targetId } : {}), ...(eventType ? { event_type: eventType } : {}) })}
          className="rounded-lg bg-slate-900 px-4 py-1.5 text-sm text-white"
        >
          Search
        </button>
      </div>

      {events.isLoading ? (
        <SkeletonRows />
      ) : events.isError ? (
        <ErrorState message={extractError(events.error)} onRetry={() => events.refetch()} />
      ) : (events.data ?? []).length === 0 ? (
        <EmptyState title="No events found" hint="Try widening the filters." />
      ) : (
        <div className="overflow-x-auto rounded-xl bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
                <th className="px-3 py-2">Timestamp</th>
                <th className="px-3 py-2">Target</th>
                <th className="px-3 py-2">Event</th>
                <th className="px-3 py-2">Actor</th>
                <th className="px-3 py-2">Result</th>
                <th className="px-3 py-2">GPS</th>
              </tr>
            </thead>
            <tbody>
              {(events.data ?? []).map((e) => (
                <tr key={e.id} className="border-b border-slate-50 last:border-0">
                  <td className="whitespace-nowrap px-3 py-2 text-xs">{new Date(e.created_at).toLocaleString()}</td>
                  <td className="px-3 py-2">
                    {e.target_type === 'unit' ? (
                      <Link to={`/dashboard/units/${e.target_id}`} className="font-mono text-xs text-brand-600 hover:underline">
                        {e.target_id}
                      </Link>
                    ) : (
                      <span className="font-mono text-xs">{e.target_id}</span>
                    )}
                  </td>
                  <td className="px-3 py-2 font-medium">{e.event_type}</td>
                  <td className="px-3 py-2 font-mono text-xs">{e.actor_org_id ?? 'system'}</td>
                  <td className="px-3 py-2">{e.resulting_state && <Badge value={e.resulting_state} />}</td>
                  <td className="px-3 py-2">
                    {e.gps_lat != null ? (
                      <Link to={`/dashboard/map?lat=${e.gps_lat}&lng=${e.gps_lng}`} className="text-brand-600">
                        <MapPin size={15} />
                      </Link>
                    ) : (
                      <span className="text-slate-300">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
