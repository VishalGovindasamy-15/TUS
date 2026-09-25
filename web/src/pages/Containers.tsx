import { useState } from 'react';
import { Link } from 'react-router-dom';
import { extractError } from '../api/client';
import { useContainer, useCreateContainer, useDisaggregate } from '../api/hooks';
import { useToast } from '../components/Toast';
import { Badge, ConfirmDialog, EmptyState, Field, Modal, inputCls } from '../components/ui';

const IDS_KEY = 'trustus_container_ids';
function loadIds(): string[] {
  try {
    return JSON.parse(localStorage.getItem(IDS_KEY) ?? '[]') as string[];
  } catch {
    return [];
  }
}

export default function Containers() {
  const { toast } = useToast();
  const [ids, setIds] = useState<string[]>(loadIds);
  const [selected, setSelected] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [confirmDis, setConfirmDis] = useState(false);
  const detail = useContainer(selected ?? undefined);
  const disaggregate = useDisaggregate();

  const save = (list: string[]) => {
    setIds(list);
    localStorage.setItem(IDS_KEY, JSON.stringify(list));
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Containers</h1>
        <button onClick={() => setShowNew(true)} className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700">
          Pack Container
        </button>
      </div>

      {ids.length === 0 ? (
        <EmptyState
          title="No containers yet"
          hint="Pack loose units into a box, or nest boxes into pallets and shipments."
          action={<button onClick={() => setShowNew(true)} className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white">Pack Container</button>}
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="space-y-2">
            {ids.map((id) => (
              <button
                key={id}
                onClick={() => setSelected(id)}
                className={`w-full truncate rounded-lg border bg-white p-3 text-left font-mono text-sm hover:border-brand-600 ${selected === id ? 'border-brand-600 ring-1 ring-brand-600' : 'border-slate-200'}`}
              >
                {id}
              </button>
            ))}
          </div>
          <div className="lg:col-span-2">
            {!selected ? (
              <EmptyState title="Select a container" />
            ) : detail.isLoading ? (
              <div className="h-32 animate-pulse rounded-xl bg-white" />
            ) : detail.data ? (
              <div className="rounded-xl bg-white p-4 shadow-sm">
                <div className="flex items-center justify-between">
                  <h2 className="font-semibold capitalize">{detail.data.container_type}</h2>
                  <div className="flex gap-2">
                    <Badge value={detail.data.disaggregated ? 'RETURNED' : detail.data.state} />
                    {!detail.data.disaggregated && (
                      <button onClick={() => setConfirmDis(true)} className="rounded-lg bg-red-600 px-3 py-1 text-xs text-white hover:bg-red-700">
                        Disaggregate
                      </button>
                    )}
                  </div>
                </div>
                <p className="mt-1 font-mono text-xs text-slate-500">{detail.data.id}</p>
                <h3 className="mb-2 mt-4 text-sm font-medium text-slate-600">Contents</h3>
                {detail.data.children.length === 0 ? (
                  <EmptyState title="Empty" hint={detail.data.disaggregated ? 'This container was disaggregated.' : 'No children packed.'} />
                ) : (
                  <div className="space-y-1">
                    {detail.data.children.map((c, i) => (
                      <div key={i} className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-1.5 text-sm">
                        {c.child_type === 'unit' ? (
                          <Link to={`/dashboard/units/${c.child_id}`} className="font-mono text-brand-600 hover:underline">{c.child_id}</Link>
                        ) : (
                          <button onClick={() => setSelected(c.child_id)} className="font-mono text-brand-600 hover:underline">{c.child_id}</button>
                        )}
                        <span className="flex items-center gap-2">
                          <span className="text-xs text-slate-500">{c.child_type}</span>
                          {c.state && <Badge value={c.state} />}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </div>
      )}

      {showNew && (
        <PackModal
          onClose={() => setShowNew(false)}
          onCreated={(id: string) => {
            save(ids.includes(id) ? ids : [...ids, id]);
            setSelected(id);
            setShowNew(false);
          }}
        />
      )}
      {confirmDis && selected && (
        <ConfirmDialog
          title="Disaggregate container?"
          body="Children are released and the container is marked disaggregated. This cannot be undone."
          confirmLabel="Disaggregate"
          busy={disaggregate.isPending}
          onCancel={() => setConfirmDis(false)}
          onConfirm={async () => {
            try {
              await disaggregate.mutateAsync(selected);
              toast('success', 'Container disaggregated');
              setConfirmDis(false);
            } catch (e) {
              toast('error', extractError(e));
            }
          }}
        />
      )}
    </div>
  );
}

function PackModal({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const create = useCreateContainer();
  const { toast } = useToast();
  const [ctype, setCtype] = useState('box');
  const [input, setInput] = useState('');
  const [unitIds, setUnitIds] = useState<string[]>([]);
  const [ctrIds, setCtrIds] = useState<string[]>([]);

  const submit = async () => {
    try {
      const c = await create.mutateAsync({ container_type: ctype, child_unit_ids: unitIds, child_container_ids: ctrIds });
      toast('success', 'Container created');
      onCreated(c.id);
    } catch (e) {
      toast('error', extractError(e));
    }
  };

  return (
    <Modal title="Pack Container" onClose={onClose}>
      <div className="space-y-3">
        <Field label="Container type">
          <select className={inputCls} value={ctype} onChange={(e) => setCtype(e.target.value)}>
            <option value="box">Box (holds units)</option>
            <option value="pallet">Pallet (holds boxes)</option>
            <option value="shipment">Shipment (holds pallets/boxes)</option>
          </select>
        </Field>
        <Field label={ctype === 'box' ? 'Scan/type unit IDs (Enter to add)' : 'Child container IDs (Enter to add)'}>
          <div className="flex gap-2">
            <input
              className={inputCls}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  const v = input.trim();
                  if (v) {
                    if (ctype === 'box') setUnitIds((l) => (l.includes(v) ? l : [...l, v]));
                    else setCtrIds((l) => (l.includes(v) ? l : [...l, v]));
                  }
                  setInput('');
                }
              }}
            />
          </div>
        </Field>
        {(ctype === 'box' ? unitIds : ctrIds).length > 0 && (
          <p className="font-mono text-xs text-slate-600">
            {(ctype === 'box' ? unitIds : ctrIds).join(', ')}
          </p>
        )}
        <button onClick={submit} disabled={create.isPending} className="w-full rounded-lg bg-brand-600 py-2 text-sm text-white disabled:opacity-50">
          {create.isPending ? 'Creating…' : 'Create container'}
        </button>
      </div>
    </Modal>
  );
}
