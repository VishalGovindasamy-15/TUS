import { useState } from 'react';
import { extractError } from '../api/client';
import { useInviteStaff, usePatchStaff, useTeam } from '../api/hooks';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../components/Toast';
import { Badge, EmptyState, ErrorState, Field, Gated, Modal, SkeletonRows, inputCls } from '../components/ui';

export default function Team() {
  const { user } = useAuth();
  const { toast } = useToast();
  const team = useTeam();
  const invite = useInviteStaff();
  const patch = usePatchStaff();
  const [showInvite, setShowInvite] = useState(false);
  const isAdmin = user?.role === 'org_admin';

  const admins = (team.data ?? []).filter((u) => u.role === 'org_admin' && u.is_active);
  const isLastAdmin = (id: string) => admins.length === 1 && admins[0].id === id;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Team</h1>
        <Gated allowed={isAdmin} reason="Only org_admin can invite staff">
          <button
            onClick={() => setShowInvite(true)}
            disabled={!isAdmin}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700 disabled:opacity-50"
          >
            Invite Staff
          </button>
        </Gated>
      </div>

      {team.isLoading ? (
        <SkeletonRows />
      ) : team.isError ? (
        <ErrorState message={extractError(team.error)} onRetry={() => team.refetch()} />
      ) : (team.data ?? []).length === 0 ? (
        <EmptyState title="No staff yet" />
      ) : (
        <div className="rounded-xl bg-white shadow-sm">
          {(team.data ?? []).map((u) => (
            <div key={u.id} className="flex flex-wrap items-center gap-2 border-b border-slate-100 p-3 last:border-0">
              <span className="font-mono text-sm">{u.phone}</span>
              <Badge value={u.is_active ? 'approved' : 'rejected'} />
              <span className="text-xs capitalize text-slate-500">{u.role.replace('_', ' ')}{u.is_active ? '' : ' · inactive'}</span>
              {isAdmin && u.id !== user?.id && (
                <span className="ml-auto flex items-center gap-2">
                  <Gated
                    allowed={!isLastAdmin(u.id)}
                    reason={isLastAdmin(u.id) ? 'Cannot demote the last active org_admin' : ''}
                  >
                    <select
                      value={u.role}
                      disabled={isLastAdmin(u.id) || patch.isPending}
                      onChange={async (e) => {
                        try {
                          await patch.mutateAsync({ id: u.id, body: { role: e.target.value } });
                          toast('success', 'Role updated');
                        } catch (err) {
                          toast('error', extractError(err));
                        }
                      }}
                      className="rounded-lg border border-slate-300 px-2 py-1 text-xs disabled:opacity-50"
                    >
                      <option value="member">member</option>
                      <option value="org_admin">org_admin</option>
                    </select>
                  </Gated>
                  <Gated
                    allowed={!isLastAdmin(u.id)}
                    reason={isLastAdmin(u.id) ? 'Cannot deactivate the last active org_admin' : ''}
                  >
                    <button
                      disabled={isLastAdmin(u.id) || patch.isPending}
                      onClick={async () => {
                        try {
                          await patch.mutateAsync({ id: u.id, body: { is_active: !u.is_active } });
                          toast('success', u.is_active ? 'User deactivated' : 'User reactivated');
                        } catch (err) {
                          toast('error', extractError(err));
                        }
                      }}
                      className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs hover:bg-slate-50 disabled:opacity-50"
                    >
                      {u.is_active ? 'Deactivate' : 'Reactivate'}
                    </button>
                  </Gated>
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {showInvite && (
        <InviteModal
          onClose={() => setShowInvite(false)}
          onInvited={async (phone: string, role: string) => {
            try {
              await invite.mutateAsync({ phone, role });
              toast('success', 'Staff invited');
              setShowInvite(false);
            } catch (e) {
              toast('error', extractError(e));
            }
          }}
          busy={invite.isPending}
        />
      )}
    </div>
  );
}

function InviteModal({ onClose, onInvited, busy }: { onClose: () => void; onInvited: (p: string, r: string) => void; busy: boolean }) {
  const [phone, setPhone] = useState('');
  const [role, setRole] = useState('member');
  return (
    <Modal title="Invite Staff" onClose={onClose}>
      <div className="space-y-3">
        <Field label="Phone">
          <input className={inputCls} value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+91…" />
        </Field>
        <Field label="Role">
          <select className={inputCls} value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="member">member</option>
            <option value="org_admin">org_admin</option>
          </select>
        </Field>
        <button onClick={() => onInvited(phone, role)} disabled={busy || !phone} className="w-full rounded-lg bg-brand-600 py-2 text-sm text-white disabled:opacity-50">
          {busy ? 'Inviting…' : 'Invite'}
        </button>
      </div>
    </Modal>
  );
}
