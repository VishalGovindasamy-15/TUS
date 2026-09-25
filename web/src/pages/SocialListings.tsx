import { useState } from 'react';
import { ShieldCheck } from 'lucide-react';
import { extractError } from '../api/client';
import { useCreateSocialListing, useDeleteSocialListing, useSocialListings, useUnit } from '../api/hooks';
import { useToast } from '../components/Toast';
import { ConfirmDialog, CopyButton, EmptyState, ErrorState, Field, Modal, SkeletonRows, inputCls } from '../components/ui';

export default function SocialListings() {
  const listings = useSocialListings();
  const del = useDeleteSocialListing();
  const { toast } = useToast();
  const [showNew, setShowNew] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Social Listings</h1>
        <button onClick={() => setShowNew(true)} className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700">
          New Listing
        </button>
      </div>

      {listings.isLoading ? (
        <SkeletonRows />
      ) : listings.isError ? (
        <ErrorState message={extractError(listings.error)} onRetry={() => listings.refetch()} />
      ) : (listings.data ?? []).length === 0 ? (
        <EmptyState
          title="No listings yet"
          hint="Link the real unit IDs in your stock to your social posts. Buyers can scan to verify authenticity — and listings with clean histories earn a Verified Seller badge that builds buyer trust."
          action={<button onClick={() => setShowNew(true)} className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white">New Listing</button>}
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {(listings.data ?? []).map((l) => (
            <div key={l.id} className="rounded-xl bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="font-medium capitalize">{l.platform}</span>
                <VerifiedBadge unitIds={l.unit_ids} />
              </div>
              <a href={l.post_url} target="_blank" rel="noreferrer" className="mt-1 block truncate text-sm text-brand-600 hover:underline">
                {l.post_url}
              </a>
              <div className="mt-2 space-y-1">
                {l.unit_ids.map((uid) => (
                  <div key={uid} className="flex items-center justify-between gap-2 rounded-lg bg-slate-50 px-2 py-1">
                    <span className="font-mono text-xs">{uid}</span>
                    <CopyButton text={`${window.location.origin}/v/${uid}`} label="Copy verify link" />
                  </div>
                ))}
              </div>
              <button
                onClick={() => setConfirmDelete(l.id)}
                className="mt-3 rounded-lg border border-red-200 px-3 py-1.5 text-xs text-red-600 hover:bg-red-50"
              >
                Delete listing
              </button>
            </div>
          ))}
        </div>
      )}

      {showNew && <NewListingModal onClose={() => setShowNew(false)} />}
      {confirmDelete && (
        <ConfirmDialog
          title="Delete listing?"
          body="The listing will be removed. This cannot be undone."
          confirmLabel="Delete"
          busy={del.isPending}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={async () => {
            try {
              await del.mutateAsync(confirmDelete);
              toast('success', 'Listing deleted');
              setConfirmDelete(null);
            } catch (e) {
              toast('error', extractError(e));
            }
          }}
        />
      )}
    </div>
  );
}

/* Badge preview exactly as a buyer would see it (spec 4.11). */
function VerifiedBadge({ unitIds }: { unitIds: string[] }) {
  const first = useUnit(unitIds[0]);
  if (first.isLoading) return null;
  const clean = first.data && first.data.current_state !== 'FLAGGED';
  if (!clean) return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-800">
      <ShieldCheck size={13} /> Verified Seller
    </span>
  );
}

function NewListingModal({ onClose }: { onClose: () => void }) {
  const create = useCreateSocialListing();
  const { toast } = useToast();
  const [platform, setPlatform] = useState('instagram');
  const [postUrl, setPostUrl] = useState('');
  const [unitInput, setUnitInput] = useState('');
  const [unitIds, setUnitIds] = useState<string[]>([]);

  const addUnit = () => {
    const id = unitInput.trim();
    if (id && !unitIds.includes(id)) setUnitIds((ids) => [...ids, id]);
    setUnitInput('');
  };

  const submit = async () => {
    try {
      await create.mutateAsync({ platform, post_url: postUrl, unit_ids: unitIds });
      toast('success', 'Listing created');
      onClose();
    } catch (e) {
      toast('error', extractError(e));
    }
  };

  return (
    <Modal title="New Listing" onClose={onClose}>
      <div className="space-y-3">
        <Field label="Platform">
          <select className={inputCls} value={platform} onChange={(e) => setPlatform(e.target.value)}>
            <option value="instagram">Instagram</option>
            <option value="whatsapp">WhatsApp</option>
            <option value="other">Other</option>
          </select>
        </Field>
        <Field label="Post URL">
          <input className={inputCls} value={postUrl} onChange={(e) => setPostUrl(e.target.value)} placeholder="https://…" />
        </Field>
        <Field label="Linked unit IDs">
          <div className="flex gap-2">
            <input
              className={inputCls}
              value={unitInput}
              onChange={(e) => setUnitInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addUnit())}
              placeholder="Scan or type a unit ID, press Enter"
            />
            <button onClick={addUnit} className="shrink-0 rounded-lg border border-slate-300 px-3 text-sm hover:bg-slate-50">
              Add
            </button>
          </div>
        </Field>
        {unitIds.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {unitIds.map((id) => (
              <span key={id} className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 font-mono text-xs">
                {id}
                <button onClick={() => setUnitIds((ids) => ids.filter((x) => x !== id))} className="text-slate-400 hover:text-red-600">×</button>
              </span>
            ))}
          </div>
        )}
        <button
          onClick={submit}
          disabled={create.isPending || !postUrl || unitIds.length === 0}
          className="w-full rounded-lg bg-brand-600 py-2 text-sm text-white disabled:opacity-50"
        >
          {create.isPending ? 'Creating…' : 'Create listing'}
        </button>
      </div>
    </Modal>
  );
}
