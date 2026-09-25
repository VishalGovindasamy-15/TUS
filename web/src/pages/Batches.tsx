import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { api, extractError } from '../api/client';
import {
  useBatch, useBatchUnits, useCreateBatch, useCreateProduct, useProducts,
} from '../api/hooks';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../components/Toast';
import { Badge, ConfirmDialog, EmptyState, Field, Modal, SkeletonRows, inputCls, Gated } from '../components/ui';
import type { Batch } from '../api/types';

const IDS_KEY = 'trustus_batch_ids';

function loadIds(): string[] {
  try {
    return JSON.parse(localStorage.getItem(IDS_KEY) ?? '[]') as string[];
  } catch {
    return [];
  }
}

export default function Batches() {
  const { org, user } = useAuth();
  const { toast } = useToast();
  const qc = useQueryClient();
  const [batchIds, setBatchIds] = useState<string[]>(loadIds);
  const [selected, setSelected] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [showRecall, setShowRecall] = useState(false);
  const [genBusy, setGenBusy] = useState(false);

  useEffect(() => localStorage.setItem(IDS_KEY, JSON.stringify(batchIds)), [batchIds]);

  const batch = useBatch(selected ?? undefined);
  /* FIX (spec 4.3): unit list lives in the React Query cache, survives navigation. */
  const units = useBatchUnits(selected ?? undefined);

  const isMfg = org?.org_type === 'manufacturer';
  const isAdmin = user?.role === 'org_admin';

  if (!isMfg) {
    return <EmptyState title="Batches are managed by manufacturers" hint="Your organisation type does not create batches." />;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Batches & Units</h1>
        <button onClick={() => setShowNew(true)} className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700">
          New Batch
        </button>
      </div>

      {batchIds.length === 0 ? (
        <EmptyState
          title="No batches yet — create your first batch"
          hint="A batch groups units of one product with shared manufacturing and expiry dates."
          action={<button onClick={() => setShowNew(true)} className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white">New Batch</button>}
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="space-y-2">
            {batchIds.map((id) => (
              <BatchRow key={id} id={id} active={id === selected} onSelect={() => setSelected(id)} />
            ))}
          </div>
          <div className="lg:col-span-2">
            {!selected ? (
              <EmptyState title="Select a batch" hint="Choose a batch on the left to manage its units." />
            ) : batch.isLoading ? (
              <SkeletonRows />
            ) : batch.isError ? (
              <p className="text-sm text-red-600">{extractError(batch.error)}</p>
            ) : batch.data ? (
              <BatchDetail
                batch={batch.data}
                units={units.data ?? []}
                unitsLoading={units.isLoading}
                genBusy={genBusy}
                onGenerate={async () => {
                  setGenBusy(true);
                  try {
                    const gen = await api.post(`/batches/${selected}/units`, {}).then((r) => r.data);
                    toast('success', `Generated ${(gen.unit_ids as string[]).length} units`);
                    qc.invalidateQueries({ queryKey: ['batch-units', selected] });
                    qc.invalidateQueries({ queryKey: ['batch', selected] });
                  } catch (e) {
                    toast('error', extractError(e));
                  } finally {
                    setGenBusy(false);
                  }
                }}
                onRecall={() => setShowRecall(true)}
                canRecall={isAdmin && !batch.data.recalled}
              />
            ) : null}
          </div>
        </div>
      )}

      {showNew && (
        <NewBatchModal
          onClose={() => setShowNew(false)}
          onCreated={(b: Batch) => {
            setBatchIds((ids) => (ids.includes(b.id) ? ids : [...ids, b.id]));
            setSelected(b.id);
            setShowNew(false);
          }}
        />
      )}
      {showRecall && selected && (
        <RecallModal
          batchId={selected}
          onClose={() => setShowRecall(false)}
          onDone={(affected, notified) => {
            toast('success', `Recalled — ${affected} units, ${notified} orgs notified`);
            setShowRecall(false);
            qc.invalidateQueries({ queryKey: ['batch', selected] });
          }}
        />
      )}
    </div>
  );
}

function BatchRow({ id, active, onSelect }: { id: string; active: boolean; onSelect: () => void }) {
  const { data, isLoading } = useBatch(id);
  if (isLoading) return <div className="h-14 animate-pulse rounded-lg bg-white" />;
  if (!data) return null;
  return (
    <button
      onClick={onSelect}
      className={`w-full rounded-lg border bg-white p-3 text-left shadow-sm hover:border-brand-600 ${active ? 'border-brand-600 ring-1 ring-brand-600' : 'border-slate-200'}`}
    >
      <div className="flex items-center justify-between">
        <span className="font-medium">{data.batch_number}</span>
        {data.recalled && <Badge value="recalled" />}
      </div>
      <div className="text-xs text-slate-500">
        {data.units_generated} units · mfg {data.mfg_date ?? '—'} · exp {data.expiry_date ?? '—'}
      </div>
    </button>
  );
}

function BatchDetail({
  batch, units, unitsLoading, genBusy, onGenerate, onRecall, canRecall,
}: {
  batch: Batch;
  units: { id: string; current_state: string }[];
  unitsLoading: boolean;
  genBusy: boolean;
  onGenerate: () => void;
  onRecall: () => void;
  canRecall: boolean;
}) {
  const { toast } = useToast();
  const [format, setFormat] = useState('csv');
  const [exporting, setExporting] = useState(false);

  const doExport = async () => {
    setExporting(true);
    try {
      const res = await api.post(`/batches/${batch.id}/export-labels`, { format }, { responseType: 'blob' });
      const url = URL.createObjectURL(res.data as Blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${batch.batch_number}_labels.${format === 'pdf_sheet' ? 'pdf' : format === 'zpl' ? 'zpl' : 'csv'}`;
      a.click();
      URL.revokeObjectURL(url);
      toast('success', 'Labels exported');
    } catch (e) {
      toast('error', extractError(e));
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="rounded-xl bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">{batch.batch_number}</h2>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={onGenerate}
            disabled={genBusy}
            className="rounded-lg bg-brand-600 px-3 py-1.5 text-sm text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {genBusy ? 'Generating…' : 'Generate Units'}
          </button>
          <select value={format} onChange={(e) => setFormat(e.target.value)} className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm">
            <option value="csv">CSV</option>
            <option value="pdf_sheet">PDF sheet</option>
            <option value="zpl">ZPL</option>
          </select>
          <button onClick={doExport} disabled={exporting || units.length === 0} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50">
            {exporting ? 'Exporting…' : 'Export Labels'}
          </button>
          <Gated allowed={canRecall} reason={batch.recalled ? 'Already recalled' : 'Only a manufacturer org_admin can recall'}>
            <button onClick={onRecall} disabled={!canRecall} className="rounded-lg bg-red-600 px-3 py-1.5 text-sm text-white hover:bg-red-700 disabled:opacity-50">
              Initiate Recall
            </button>
          </Gated>
        </div>
      </div>
      {batch.recalled && (
        <p className="mt-2 rounded-lg bg-orange-50 px-3 py-2 text-sm text-orange-800">
          Recalled: {batch.recall_reason}
        </p>
      )}
      <h3 className="mb-2 mt-4 text-sm font-medium text-slate-600">
        Units ({unitsLoading ? '…' : units.length})
      </h3>
      {unitsLoading ? (
        <SkeletonRows rows={3} />
      ) : units.length === 0 ? (
        <EmptyState title="No units generated yet" hint="Generate units to get printable QR label data." />
      ) : (
        <div className="max-h-96 space-y-1 overflow-auto">
          {units.map((u) => (
            <Link key={u.id} to={`/dashboard/units/${u.id}`} className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-1.5 text-sm hover:bg-slate-50">
              <span className="font-mono">{u.id}</span>
              <Badge value={u.current_state} />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function NewBatchModal({ onClose, onCreated }: { onClose: () => void; onCreated: (b: Batch) => void }) {
  const products = useProducts();
  const createProduct = useCreateProduct();
  const createBatch = useCreateBatch();
  const { toast } = useToast();
  const [productId, setProductId] = useState('');
  const [batchNumber, setBatchNumber] = useState('');
  const [quantity, setQuantity] = useState(100);
  const [mfgDate, setMfgDate] = useState('');
  const [expiryDate, setExpiryDate] = useState('');
  const [newCode, setNewCode] = useState('');
  const [newName, setNewName] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      let pid = productId;
      if (!pid) {
        const p = await createProduct.mutateAsync({ product_code: newCode, name: newName, category: 'pharma' });
        pid = (p as { id: string }).id;
      }
      const b = (await createBatch.mutateAsync({
        product_id: pid, batch_number: batchNumber, quantity,
        mfg_date: mfgDate || null, expiry_date: expiryDate || null,
      })) as Batch;
      toast('success', 'Batch created');
      onCreated(b);
    } catch (e) {
      toast('error', extractError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="New Batch" onClose={onClose}>
      <div className="space-y-3">
        <Field label="Product">
          <select className={inputCls} value={productId} onChange={(e) => setProductId(e.target.value)}>
            <option value="">— New product —</option>
            {(products.data ?? []).map((p) => (
              <option key={p.id} value={p.id}>{p.product_code} — {p.name}</option>
            ))}
          </select>
        </Field>
        {!productId && (
          <div className="grid grid-cols-2 gap-2">
            <Field label="Product code">
              <input className={inputCls} value={newCode} onChange={(e) => setNewCode(e.target.value)} />
            </Field>
            <Field label="Product name">
              <input className={inputCls} value={newName} onChange={(e) => setNewName(e.target.value)} />
            </Field>
          </div>
        )}
        <Field label="Batch number">
          <input className={inputCls} value={batchNumber} onChange={(e) => setBatchNumber(e.target.value)} />
        </Field>
        <div className="grid grid-cols-3 gap-2">
          <Field label="Quantity">
            <input type="number" min={1} className={inputCls} value={quantity} onChange={(e) => setQuantity(Number(e.target.value))} />
          </Field>
          <Field label="Mfg date">
            <input type="date" className={inputCls} value={mfgDate} onChange={(e) => setMfgDate(e.target.value)} />
          </Field>
          <Field label="Expiry date">
            <input type="date" className={inputCls} value={expiryDate} onChange={(e) => setExpiryDate(e.target.value)} />
          </Field>
        </div>
        <button onClick={submit} disabled={busy} className="w-full rounded-lg bg-brand-600 py-2 text-sm text-white hover:bg-brand-700 disabled:opacity-50">
          {busy ? 'Creating…' : 'Create batch'}
        </button>
      </div>
    </Modal>
  );
}

function RecallModal({ batchId, onClose, onDone }: { batchId: string; onClose: () => void; onDone: (a: number, n: number) => void }) {
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ affected_units: number; affected_orgs_notified: number } | null>(null);
  const { toast } = useToast();

  const submit = async () => {
    setBusy(true);
    try {
      const res = await api.post(`/batches/${batchId}/recall`, { reason });
      setResult(res.data);
    } catch (e) {
      toast('error', extractError(e));
    } finally {
      setBusy(false);
    }
  };

  if (result) {
    return (
      <Modal title="Recall initiated" onClose={() => onDone(result.affected_units, result.affected_orgs_notified)}>
        <p className="text-sm">
          Affected units: <strong>{result.affected_units}</strong>
          <br />
          Organisations notified: <strong>{result.affected_orgs_notified}</strong>
        </p>
        <button
          onClick={() => onDone(result.affected_units, result.affected_orgs_notified)}
          className="mt-4 w-full rounded-lg bg-brand-600 py-2 text-sm text-white"
        >
          Done
        </button>
      </Modal>
    );
  }

  return (
    <Modal title="Initiate Recall" onClose={onClose}>
      <Field label="Type the reason (required)">
        <input className={inputCls} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. suspected contamination in lot" />
      </Field>
      <p className="mt-2 text-xs text-slate-500">
        This marks the batch recalled. Consumers verifying these units will see a recalled warning. This cannot be undone from the UI.
      </p>
      <button
        onClick={submit}
        disabled={busy || reason.trim().length < 3}
        className="mt-3 w-full rounded-lg bg-red-600 py-2 text-sm text-white hover:bg-red-700 disabled:opacity-50"
      >
        {busy ? 'Recalling…' : 'Confirm recall'}
      </button>
    </Modal>
  );
}
