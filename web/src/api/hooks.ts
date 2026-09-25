import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type {
  AlertItem, Batch, ContainerOut, CustodyEvent, DisclosureField, FraudPatterns,
  Invite, KycDoc, NetworkTree, OrgOut, Product, RegulatorGrant, SessionOut,
  SocialListing, Unit, UserOut, VerifyResult,
} from './types';

const get = async <T,>(url: string, params?: Record<string, unknown>): Promise<T> =>
  (await api.get(url, { params })).data;

/* ---------------- org & users ---------------- */
export const useOrg = (enabled = true) =>
  useQuery({ queryKey: ['org'], queryFn: () => get<OrgOut>('/orgs/me'), enabled, retry: false });

export const useTeam = () =>
  useQuery({ queryKey: ['team'], queryFn: () => get<UserOut[]>('/orgs/me/users') });

export const useInviteStaff = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { phone: string; role: string }) =>
      api.post('/orgs/me/users/invite', body).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['team'] }),
  });
};

export const usePatchStaff = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api.patch(`/orgs/me/users/${id}`, body).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['team'] }),
  });
};

export const useNotifSettings = () =>
  useQuery({
    queryKey: ['notif-settings'],
    queryFn: () => get<{ channels: string[]; language: string }>('/orgs/me/notification-settings'),
  });

export const useSaveNotifSettings = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { channels: string[]; language: string }) =>
      api.patch('/orgs/me/notification-settings', body).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notif-settings'] }),
  });
};

export const useKycDocs = (orgId: string | undefined) =>
  useQuery({
    queryKey: ['kyc-docs', orgId],
    queryFn: () => get<KycDoc[]>(`/orgs/${orgId}/kyc-documents`),
    enabled: !!orgId,
  });

export const useSessions = () =>
  useQuery({ queryKey: ['sessions'], queryFn: () => get<SessionOut[]>('/auth/sessions') });

export const useRevokeSession = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post(`/auth/sessions/${id}/revoke`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sessions'] }),
  });
};

/* ---------------- products & batches ---------------- */
export const useProducts = () =>
  useQuery({ queryKey: ['products'], queryFn: () => get<Product[]>('/products') });

export const useCreateProduct = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post('/products', body).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['products'] }),
  });
};

/* NOTE: the server has no list-batches route; the page keeps created batches in
   local state + React Query per-batch cache (see Batches page). */
export const useBatch = (batchId: string | undefined) =>
  useQuery({
    queryKey: ['batch', batchId],
    queryFn: () => get<Batch>(`/batches/${batchId}`),
    enabled: !!batchId,
  });

export const useCreateBatch = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post('/batches', body).then((r) => r.data),
    onSuccess: (data: Batch) => {
      qc.setQueryData(['batch', data.id], data);
      qc.invalidateQueries({ queryKey: ['batch-ids'] });
    },
  });
};

export const useBatchUnits = (batchId: string | undefined) =>
  useQuery({
    queryKey: ['batch-units', batchId],
    queryFn: () => get<Unit[]>(`/batches/${batchId}/units`),
    enabled: !!batchId,
  });

export const useGenerateUnits = (batchId: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (count?: number) =>
      api.post(`/batches/${batchId}/units`, count ? { count } : {}).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['batch-units', batchId] });
      qc.invalidateQueries({ queryKey: ['batch', batchId] });
    },
  });
};

export const useRecallBatch = (batchId: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (reason: string) =>
      api.post(`/batches/${batchId}/recall`, { reason }).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['batch', batchId] }),
  });
};

/* ---------------- units & verify ---------------- */
export const useUnit = (unitId: string | undefined) =>
  useQuery({
    queryKey: ['unit', unitId],
    queryFn: () => get<Unit>(`/units/${unitId}`),
    enabled: !!unitId,
  });

export const useUnitHistory = (unitId: string | undefined) =>
  useQuery({
    queryKey: ['unit-history', unitId],
    queryFn: () => get<CustodyEvent[]>(`/units/${unitId}/history`),
    enabled: !!unitId,
  });

export const useVerify = (unitId: string | undefined) =>
  useQuery({
    queryKey: ['verify', unitId],
    queryFn: () => get<VerifyResult>(`/verify/${unitId}`),
    enabled: !!unitId,
    retry: false,
  });

/* ---------------- network ---------------- */
export const useNetworkTree = () =>
  useQuery({ queryKey: ['network-tree'], queryFn: () => get<NetworkTree>('/network/tree') });

export const useCreateInvite = () =>
  useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post('/network/invites', body).then((r) => r.data as Invite),
  });

export const useAcceptInvite = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (code: string) =>
      api.post(`/network/invites/${code}/accept`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['network-tree'] }),
  });
};

/* ---------------- events & alerts ---------------- */
export interface EventFilters {
  target_id?: string; event_type?: string; date_from?: string; date_to?: string; limit?: number;
}
export const useEvents = (filters: EventFilters = {}, refetchInterval?: number) =>
  useQuery({
    queryKey: ['events', filters],
    queryFn: () => get<CustodyEvent[]>('/events', { ...filters, limit: filters.limit ?? 200 }),
    refetchInterval,
  });

export const useAlerts = (params: Record<string, string> = {}) =>
  useQuery({ queryKey: ['alerts', params], queryFn: () => get<AlertItem[]>('/alerts', params) });

export const useReviewAlert = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.patch(`/alerts/${id}`, { status: 'reviewed' }).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts'] });
      qc.invalidateQueries({ queryKey: ['admin-alerts'] });
    },
  });
};

/* ---------------- social listings ---------------- */
export const useSocialListings = () =>
  useQuery({ queryKey: ['social-listings'], queryFn: () => get<SocialListing[]>('/social-listings') });

export const useCreateSocialListing = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post('/social-listings', body).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['social-listings'] }),
  });
};

export const useDeleteSocialListing = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/social-listings/${id}`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['social-listings'] }),
  });
};

/* ---------------- containers ---------------- */
export const useCreateContainer = () =>
  useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post('/containers', body).then((r) => r.data as ContainerOut),
  });

export const useContainer = (id: string | undefined) =>
  useQuery({
    queryKey: ['container', id],
    queryFn: () => get<ContainerOut>(`/containers/${id}`),
    enabled: !!id,
  });

export const useDisaggregate = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post(`/containers/${id}/disaggregate`).then((r) => r.data),
    onSuccess: (_d, id) => qc.invalidateQueries({ queryKey: ['container', id] }),
  });
};

/* ---------------- disclosures ---------------- */
export const useDisclosureFields = (category: string) =>
  useQuery({
    queryKey: ['disclosure-fields', category],
    queryFn: () => get<DisclosureField[]>('/disclosure-fields', { category }),
    enabled: !!category,
  });

/* ---------------- admin ---------------- */
export interface AdminOrg extends OrgOut { kyc_documents: KycDoc[] }
export const useAdminOrgs = (status?: string) =>
  useQuery({
    queryKey: ['admin-orgs', status],
    queryFn: () => get<AdminOrg[]>('/admin/orgs', status ? { status } : {}),
  });

export const useApproveOrg = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post(`/admin/orgs/${id}/approve`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-orgs'] }),
  });
};

export const useRejectOrg = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      api.post(`/admin/orgs/${id}/reject`, { reason }).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-orgs'] }),
  });
};

export const useFraudPatterns = () =>
  useQuery({ queryKey: ['fraud-patterns'], queryFn: () => get<FraudPatterns>('/admin/fraud-patterns') });

export const useRegulatorGrants = () =>
  useQuery({ queryKey: ['regulator-grants'], queryFn: () => get<RegulatorGrant[]>('/admin/regulator-access') });

export const useCreateRegulatorGrant = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post('/admin/regulator-access', body).then((r) => r.data as RegulatorGrant),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['regulator-grants'] }),
  });
};

export const useRevokeRegulatorGrant = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.post(`/admin/regulator-access/${id}/revoke`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['regulator-grants'] }),
  });
};

export const useAdminAlerts = (params: Record<string, string> = {}) =>
  useQuery({
    queryKey: ['admin-alerts', params],
    queryFn: () => get<AlertItem[]>('/admin/alerts', params),
  });
