import { useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { MapContainer, Marker, Popup, TileLayer } from 'react-leaflet';
import L from 'leaflet';
import { extractError } from '../api/client';
import { useEvents } from '../api/hooks';
import { EmptyState, ErrorState, SkeletonRows } from '../components/ui';
import type { CustodyEvent } from '../api/types';

interface Cluster { lat: number; lng: number; events: CustodyEvent[] }

function clusterize(events: CustodyEvent[]): Cluster[] {
  const cells = new Map<string, Cluster>();
  for (const e of events) {
    if (e.gps_lat == null || e.gps_lng == null) continue;
    const key = `${e.gps_lat.toFixed(1)},${e.gps_lng.toFixed(1)}`;
    const c = cells.get(key) ?? { lat: e.gps_lat, lng: e.gps_lng, events: [] };
    c.events.push(e);
    cells.set(key, c);
  }
  return [...cells.values()];
}

export default function LiveMap() {
  const [params] = useSearchParams();
  /* FIX (spec 4.7): real org-scoped event data, auto-refresh every 60s. */
  const events = useEvents({ limit: 300 }, 60_000);

  const clusters = useMemo(() => clusterize(events.data ?? []), [events.data]);
  const focus: [number, number] | null =
    params.get('lat') && params.get('lng')
      ? [Number(params.get('lat')), Number(params.get('lng'))]
      : clusters[0]
        ? [clusters[0].lat, clusters[0].lng]
        : null;

  if (events.isLoading) return <SkeletonRows />;
  if (events.isError) return <ErrorState message={extractError(events.error)} onRetry={() => events.refetch()} />;
  if (clusters.length === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-bold">Live Map</h1>
        <EmptyState
          title="No GPS-tagged scans yet"
          hint="GPS is optional on scans, so a new organisation often has no map data. Locations appear here automatically as field scans with GPS come in."
        />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Live Map</h1>
        <span className="text-xs text-slate-500">Auto-refreshes every 60s</span>
      </div>
      <MapContainer center={focus ?? [20.59, 78.96]} zoom={focus ? 10 : 5} style={{ height: 560 }}>
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="© OpenStreetMap" />
        {clusters.map((c, i) => (
          <Marker
            key={i}
            position={[c.lat, c.lng]}
            icon={
              c.events.length > 1
                ? L.divIcon({ className: '', html: `<div class="cluster-badge">${c.events.length}</div>`, iconSize: [34, 34] })
                : L.divIcon({ className: '', html: '<div class="pin-badge" style="background:#1d4ed8"></div>', iconSize: [16, 16] })
            }
          >
            <Popup>
              <div className="space-y-1 text-xs">
                {c.events.slice(0, 5).map((e) => (
                  <div key={e.id}>
                    <strong>{e.event_type}</strong>{' '}
                    <Link to={`/dashboard/units/${e.target_id}`} className="font-mono text-blue-700 underline">
                      {e.target_id}
                    </Link>
                  </div>
                ))}
                {c.events.length > 5 && <div>+{c.events.length - 5} more</div>}
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
