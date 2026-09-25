import { useState } from 'react';
import { extractError } from '../api/client';
import { useAcceptInvite, useCreateInvite, useNetworkTree } from '../api/hooks';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../components/Toast';
import { Badge, CopyButton, EmptyState, ErrorState, Field, Gated, Modal, SkeletonRows, inputCls } from '../components/ui';
import type { Invite } from '../api/types';

const CAN_INVITE = ['manufacturer', 'regional_agent', 'distributor_authorized'];

export default function Network() {
  const { org } = useAuth();
  const tree = useNetworkTree();
  const [showInvite, setShowInvite] = useState(false);
  const [showAccept, setShowAccept] = useState(false);
  const canInvite = CAN_INVITE.includes(org?.org_type ?? '');

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Network</h1>
        <div className="flex gap-2">
          <button onClick={() => setShowAccept(true)} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm hover:bg-slate-50">
            Accept Invite
          </button>
          <Gated allowed={canInvite} reason={`${org?.org_type} cannot extend the network`}>
            <button
              onClick={() => setShowInvite(true)}
              disabled={!canInvite}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700 disabled:opacity-50"
            >
              Invite Partner
            </button>
          </Gated>
        </div>
      </div>

      {tree.isLoading ? (
        <SkeletonRows />
      ) : tree.isError ? (
        <ErrorState message={extractError(tree.error)} onRetry={() => tree.refetch()} />
      ) : (tree.data?.edges ?? []).length === 0 ? (
        <EmptyState
          title="No network connections yet"
          hint="Invite downstream partners so their scans are authorized on your products."
          action={canInvite ? (
            <button onClick={() => setShowInvite(true)} className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white">Invite Partner</button>
          ) : undefined}
        />
      ) : (
        <div className="rounded-xl bg-white p-4 shadow-sm">
          {tree.data!.edges.map((e, i) => {
            const node = (id: string) => tree.data!.nodes.find((n) => n.org_id === id);
            const from = node(e.from_org_id);
            const to = node(e.to_org_id);
            return (
              <div key={i} className="flex flex-wrap items-center gap-2 border-b border-slate-100 py-2.5 text-sm last:border-0">
                <span className="font-medium">{from?.name ?? e.from_org_id}</span>
                <span className="text-slate-400">→</span>
                <span className="font-medium">{to?.name ?? e.to_org_id}</span>
                <span className="text-xs capitalize text-slate-500">({to?.org_type.replaceAll('_', ' ')})</span>
                <Badge value={e.authorized ? 'authorized' : 'unauthorized'} />
                {e.product_code && (
                  <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs">{e.product_code}</span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {showInvite && <InviteModal onClose={() => setShowInvite(false)} />}
      {showAccept && <AcceptModal onClose={() => setShowAccept(false)} />}
    </div>
  );
}

function InviteModal({ onClose }: { onClose: () => void }) {
  const create = useCreateInvite();
  const [productCode, setProductCode] = useState('');
  const [authorized, setAuthorized] = useState(true);
  const [invite, setInvite] = useState<Invite | null>(null);
  const [error, setError] = useState('');

  const submit = async () => {
    setError('');
    try {
      const inv = await create.mutateAsync({
        product_code: productCode || null,
        authorized,
        expires_in_days: 30,
      });
      setInvite(inv);
    } catch (e) {
      setError(extractError(e));
    }
  };

  return (
    <Modal title="Invite Partner" onClose={onClose}>
      {invite ? (
        <div className="space-y-3 text-center">
          <p className="text-sm text-slate-600">Share this code/link with your partner:</p>
          <p className="rounded-lg bg-slate-100 p-3 font-mono text-lg font-bold">{invite.code}</p>
          <CopyButton text={invite.code} label="Copy code" />
        </div>
      ) : (
        <div className="space-y-3">
          <Field label="Product code (blank = all products)">
            <input className={inputCls} value={productCode} onChange={(e) => setProductCode(e.target.value)} />
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={authorized} onChange={(e) => setAuthorized(e.target.checked)} />
            Authorized tier (uncheck for lower-trust sub-tier)
          </label>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button onClick={submit} disabled={create.isPending} className="w-full rounded-lg bg-brand-600 py-2 text-sm text-white disabled:opacity-50">
            {create.isPending ? 'Creating…' : 'Generate invite'}
          </button>
        </div>
      )}
    </Modal>
  );
}

function AcceptModal({ onClose }: { onClose: () => void }) {
  const accept = useAcceptInvite();
  const { toast } = useToast();
  const [code, setCode] = useState('');
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    setError('');
    try {
      await accept.mutateAsync(code.trim());
      setDone(true);
      toast('success', 'Partner invite accepted');
    } catch (e) {
      setError(extractError(e));
    }
  };

  return (
    <Modal title="Accept Invite" onClose={onClose}>
      {done ? (
        <p className="text-sm text-emerald-700">Invite accepted — the partnership is now active.</p>
      ) : (
        <div className="space-y-3">
          <Field label="Invite code">
            <input className={inputCls} value={code} onChange={(e) => setCode(e.target.value)} placeholder="TU-XXXXXX" />
          </Field>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button onClick={submit} disabled={accept.isPending || !code} className="w-full rounded-lg bg-brand-600 py-2 text-sm text-white disabled:opacity-50">
            {accept.isPending ? 'Accepting…' : 'Accept'}
          </button>
        </div>
      )}
    </Modal>
  );
}
