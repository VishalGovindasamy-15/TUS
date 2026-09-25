import { useState } from 'react';
import { extractError } from '../../api/client';
import { useCreateRegulatorGrant, useRegulatorGrants, useRevokeRegulatorGrant } from '../../api/hooks';
import { useToast } from '../../components/Toast';
import { ConfirmDialog, EmptyState, ErrorState, Field, SkeletonRows, inputCls } from '../../components/ui';
import type { RegulatorGrant } from '../../api/types';

export default function RegulatorAccess() {
  const grants = useRegulatorGrants();
  const create = useCreateRegulatorGrant();
  const revoke = useRevokeRegulatorGrant();
  const { toast } = useToast();
  const [regulatorId, setRegulatorId] = useState('');
  const [batchId, setBatchId] = useState('');
  const [hours, setHours] = useState(72);
  const [reason, setReason] = useState('');
  const [created, setCreated] = useState<RegulatorGrant | null>(null);
  const [revoking, setRevoking] = useState<string | null>(null);

  const submit = async () => {
    try {
      const g = await create.mutateAsync({
        regulator_user_id: regulatorId, batch_id: batchId,
        expires_in_hours: hours, reason,
      });
      setCreated(g);
      setRegulatorId('');
      setBatchId('');
      setReason('');
    } catch (e) {
      toast('error', extractError(e));
    }
  };

  return (
    <div className="grid max-w-4xl gap-4 lg:grid-cols-2">
      <div className="space-y-4">
        <h1 className="text-xl font-bold">Regulator Access</h1>
        <div className="rounded-xl bg-white p-4 shadow-sm">
          <div className="space-y-3">
            <Field label="Regulator user ID">
              <input className={inputCls} value={regulatorId} onChange={(e) => setRegulatorId(e.target.value)} />
            </Field>
            <Field label="Batch ID">
              <input className={inputCls} value={batchId} onChange={(e) => setBatchId(e.target.value)} placeholder="bat_…" />
            </Field>
            <Field label="Expires in (hours)">
              <input type="number" min={1} className={inputCls} value={hours} onChange={(e) => setHours(Number(e.target.value))} />
            </Field>
            <Field label="Reason">
              <input className={inputCls} value={reason} onChange={(e) => setReason(e.target.value)} />
            </Field>
            <button
              onClick={submit}
              disabled={create.isPending || !regulatorId || !batchId || reason.trim().length < 3}
              className="w-full rounded-lg bg-brand-600 py-2 text-sm text-white disabled:opacity-50"
            >
              {create.isPending ? 'Granting…' : 'Grant access'}
            </button>
          </div>
        </div>
        {created && (
          <div className="rounded-xl border border-emerald-300 bg-emerald-50 p-4 text-sm">
            <p className="font-semibold text-emerald-800">Access granted</p>
            <p className="mt-1 font-mono text-xs">grant: {created.id}</p>
            <p className="text-xs">expires: {new Date(created.expires_at).toLocaleString()}</p>
          </div>
        )}
      </div>
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Grants</h2>
        {grants.isLoading ? (
          <SkeletonRows />
        ) : grants.isError ? (
          <ErrorState message={extractError(grants.error)} onRetry={() => grants.refetch()} />
        ) : (grants.data ?? []).length === 0 ? (
          <EmptyState title="No grants yet" />
        ) : (
          <div className="space-y-2">
            {(grants.data ?? []).map((g) => (
              <div key={g.id} className="rounded-xl bg-white p-3 text-sm shadow-sm">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{g.regulator_user_id}</span>
                  {!g.revoked_at && new Date(g.expires_at) > new Date() && (
                    <button onClick={() => setRevoking(g.id)} className="rounded-lg border border-red-200 px-2.5 py-1 text-xs text-red-600 hover:bg-red-50">
                      Revoke
                    </button>
                  )}
                </div>
                <p className="font-mono text-xs text-slate-500">batch {g.batch_id}</p>
                <p className="text-xs text-slate-500">
                  {g.revoked_at ? `revoked ${new Date(g.revoked_at).toLocaleString()}` : `expires ${new Date(g.expires_at).toLocaleString()}`}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
      {revoking && (
        <ConfirmDialog
          title="Revoke grant early?"
          body="The regulator will immediately lose access to this batch."
          confirmLabel="Revoke"
          busy={revoke.isPending}
          onCancel={() => setRevoking(null)}
          onConfirm={async () => {
            try {
              await revoke.mutateAsync(revoking);
              toast('success', 'Grant revoked');
              setRevoking(null);
            } catch (e) {
              toast('error', extractError(e));
            }
          }}
        />
      )}
    </div>
  );
}
