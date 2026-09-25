import { useState } from 'react';
import { extractError } from '../../api/client';
import { useAdminOrgs, useApproveOrg, useRejectOrg } from '../../api/hooks';
import { useToast } from '../../components/Toast';
import { Badge, ConfirmDialog, EmptyState, ErrorState, Field, Gated, SkeletonRows, inputCls } from '../../components/ui';

export default function OrgApprovals() {
  const [status, setStatus] = useState('pending');
  const orgs = useAdminOrgs(status || undefined);
  const approve = useApproveOrg();
  const reject = useRejectOrg();
  const { toast } = useToast();
  const [expanded, setExpanded] = useState<string | null>(null);
  const [viewed, setViewed] = useState<Set<string>>(new Set());
  const [rejecting, setRejecting] = useState<string | null>(null);
  const [reason, setReason] = useState('');

  const markViewed = (orgId: string, docId: string) => {
    setViewed((v) => new Set(v).add(`${orgId}:${docId}`));
  };
  const orgViewed = (orgId: string, count: number) =>
    count === 0 || [...viewed].some((k) => k.startsWith(`${orgId}:`));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Org Approvals</h1>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm">
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="">All</option>
        </select>
      </div>

      {orgs.isLoading ? (
        <SkeletonRows />
      ) : orgs.isError ? (
        <ErrorState message={extractError(orgs.error)} onRetry={() => orgs.refetch()} />
      ) : (orgs.data ?? []).length === 0 ? (
        <EmptyState title="No organisations in this state" />
      ) : (
        <div className="space-y-2">
          {(orgs.data ?? []).map((o) => (
            <div key={o.id} className="rounded-xl bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-center gap-2">
                <button onClick={() => setExpanded(expanded === o.id ? null : o.id)} className="font-medium hover:underline">
                  {o.name}
                </button>
                <span className="text-xs capitalize text-slate-500">{o.org_type.replaceAll('_', ' ')}</span>
                <Badge value={o.approval_status} />
                {o.approval_status === 'pending' && (
                  <span className="ml-auto flex gap-2">
                    <Gated
                      allowed={orgViewed(o.id, o.kyc_documents.length)}
                      reason="View at least one KYC document before approving"
                    >
                      <button
                        disabled={!orgViewed(o.id, o.kyc_documents.length) || approve.isPending}
                        onClick={async () => {
                          try {
                            await approve.mutateAsync(o.id);
                            toast('success', `${o.name} approved`);
                          } catch (e) {
                            toast('error', extractError(e));
                          }
                        }}
                        className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm text-white hover:bg-emerald-700 disabled:opacity-50"
                      >
                        Approve
                      </button>
                    </Gated>
                    <button
                      onClick={() => { setRejecting(o.id); setReason(''); }}
                      className="rounded-lg border border-red-200 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50"
                    >
                      Reject
                    </button>
                  </span>
                )}
              </div>
              {o.rejection_reason && (
                <p className="mt-1 text-xs text-red-600">Rejected: {o.rejection_reason}</p>
              )}
              {expanded === o.id && (
                <div className="mt-3 border-t border-slate-100 pt-3">
                  <p className="mb-2 text-sm font-medium text-slate-600">
                    KYC documents ({o.kyc_documents.length})
                  </p>
                  {o.kyc_documents.length === 0 ? (
                    <p className="text-sm text-slate-500">No documents submitted.</p>
                  ) : (
                    <div className="space-y-1.5">
                      {o.kyc_documents.map((d) => (
                        <div key={d.id} className="flex items-center gap-2 text-sm">
                          <span>{d.document_type.replaceAll('_', ' ')}</span>
                          <Badge value={d.status === 'approved' ? 'approved' : d.status === 'rejected' ? 'rejected' : 'pending'} />
                          <a
                            href={d.file_url}
                            target="_blank"
                            rel="noreferrer"
                            onClick={() => markViewed(o.id, d.id)}
                            className="ml-auto text-xs text-brand-600 hover:underline"
                          >
                            View Document
                          </a>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {rejecting && (
        <ConfirmDialog
          title="Reject organisation?"
          body={
            <Field label="Reason (required)">
              <input className={inputCls} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. invalid GST certificate" />
            </Field>
          }
          confirmLabel="Reject"
          busy={reject.isPending}
          onCancel={() => setRejecting(null)}
          onConfirm={async () => {
            if (reason.trim().length < 3) {
              toast('error', 'A reason is required');
              return;
            }
            try {
              await reject.mutateAsync({ id: rejecting, reason });
              toast('success', 'Organisation rejected');
              setRejecting(null);
            } catch (e) {
              toast('error', extractError(e));
            }
          }}
        />
      )}
    </div>
  );
}
