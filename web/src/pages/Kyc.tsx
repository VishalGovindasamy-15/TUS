import { useState } from 'react';
import axios from 'axios';
import { api, ensureFreshToken, extractError } from '../api/client';
import { useKycDocs } from '../api/hooks';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../components/Toast';
import { Badge, EmptyState, ErrorState, Field, SkeletonRows, inputCls } from '../components/ui';

export default function Kyc() {
  const { org } = useAuth();
  const { toast } = useToast();
  const docs = useKycDocs(org?.id);
  const [docType, setDocType] = useState('gst_certificate');
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const upload = async () => {
    if (!file || !org) return;
    setBusy(true);
    setError('');
    try {
      /* FIX 1 (spec 4.10): proactively refresh before upload so a routine token
         refresh mid-transfer can't trigger the global logout redirect. */
      const fresh = await ensureFreshToken(60);
      if (!fresh) {
        setError('Your session expired — please log in again to continue uploading.');
        return;
      }
      const form = new FormData();
      form.append('document_type', docType);
      form.append('file', file);
      await api.post(`/orgs/${org.id}/kyc-documents`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      toast('success', 'Document uploaded');
      setFile(null);
      docs.refetch();
    } catch (e) {
      /* FIX 2: genuine expiry shows an inline message, not a silent redirect. */
      if (axios.isAxiosError(e) && e.response?.status === 401) {
        setError('Your session expired — please log in again to continue uploading.');
      } else {
        setError(extractError(e));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-xl font-bold">KYC Upload</h1>

      {/* FIX 3: show already-uploaded documents + review status. */}
      <div className="rounded-xl bg-white p-4 shadow-sm">
        <h2 className="mb-2 font-semibold">Submitted documents</h2>
        {docs.isLoading ? (
          <SkeletonRows rows={2} />
        ) : docs.isError ? (
          <ErrorState message={extractError(docs.error)} onRetry={() => docs.refetch()} />
        ) : (docs.data ?? []).length === 0 ? (
          <EmptyState title="No documents submitted yet" />
        ) : (
          <div className="space-y-2">
            {(docs.data ?? []).map((d) => (
              <div key={d.id} className="flex flex-wrap items-center gap-2 border-b border-slate-100 py-2 text-sm last:border-0">
                <span className="font-medium">{d.document_type.replaceAll('_', ' ')}</span>
                <Badge value={d.status === 'approved' ? 'approved' : d.status === 'rejected' ? 'rejected' : 'pending'} />
                <span className="text-xs text-slate-500">{new Date(d.uploaded_at).toLocaleDateString()}</span>
                <a href={d.file_url} target="_blank" rel="noreferrer" className="ml-auto text-xs text-brand-600 hover:underline">
                  View
                </a>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-xl bg-white p-4 shadow-sm">
        <h2 className="mb-3 font-semibold">Upload a document</h2>
        <div className="space-y-3">
          <Field label="Document type">
            <select className={inputCls} value={docType} onChange={(e) => setDocType(e.target.value)}>
              <option value="gst_certificate">GST Certificate</option>
              <option value="drug_licence">Drug Licence</option>
              <option value="industry_license">Industry Licence</option>
              <option value="shop_license">Shop / Trade Licence</option>
              <option value="dealer_certificate">Dealer Certificate</option>
              <option value="other">Other</option>
            </select>
          </Field>
          <Field label="File">
            <input
              type="file"
              className={inputCls}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </Field>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button onClick={upload} disabled={busy || !file} className="w-full rounded-lg bg-brand-600 py-2 text-sm text-white disabled:opacity-50">
            {busy ? 'Uploading…' : 'Upload'}
          </button>
        </div>
      </div>
    </div>
  );
}
