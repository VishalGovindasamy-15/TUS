import React, { useState } from 'react';
import { AlertTriangle, Inbox, RefreshCw } from 'lucide-react';

/* ---------- shared loading / empty / error pattern (spec section 6) ---------- */
export function SkeletonRows({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-2" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-12 animate-pulse rounded-lg bg-slate-200" />
      ))}
    </div>
  );
}

export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
      <Inbox className="text-slate-400" size={28} />
      <p className="font-medium text-slate-700">{title}</p>
      {hint && <p className="max-w-md text-sm text-slate-500">{hint}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-6 py-10 text-center">
      <AlertTriangle className="text-red-500" size={28} />
      <p className="text-sm text-red-700">{message}</p>
      <button
        onClick={onRetry}
        className="mt-1 inline-flex items-center gap-1.5 rounded-lg bg-red-600 px-3 py-1.5 text-sm text-white hover:bg-red-700"
      >
        <RefreshCw size={14} /> Retry
      </button>
    </div>
  );
}

/* ---------- modal + destructive confirm ---------- */
export function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-xl bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button onClick={onClose} className="rounded px-2 py-1 text-xl text-slate-400 hover:bg-slate-100">×</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function ConfirmDialog({
  title, body, confirmLabel = 'Confirm', danger = true, busy = false,
  onConfirm, onCancel,
}: {
  title: string; body: React.ReactNode; confirmLabel?: string; danger?: boolean;
  busy?: boolean; onConfirm: () => void; onCancel: () => void;
}) {
  return (
    <Modal title={title} onClose={onCancel}>
      <div className="text-sm text-slate-600">{body}</div>
      <div className="mt-5 flex justify-end gap-2">
        <button onClick={onCancel} className="rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-50">
          Cancel
        </button>
        <button
          onClick={onConfirm}
          disabled={busy}
          className={`rounded-lg px-4 py-2 text-sm text-white disabled:opacity-50 ${
            danger ? 'bg-red-600 hover:bg-red-700' : 'bg-brand-600 hover:bg-brand-700'
          }`}
        >
          {busy ? 'Working…' : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}

/* ---------- form bits ---------- */
export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-600">{label}</span>
      {children}
    </label>
  );
}

export const inputCls =
  'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600';

/* ---------- badges ---------- */
const badgeColors: Record<string, string> = {
  genuine: 'bg-emerald-100 text-emerald-800',
  flagged: 'bg-red-100 text-red-800',
  recalled: 'bg-orange-100 text-orange-800',
  not_yet_in_circulation: 'bg-slate-200 text-slate-700',
  ISSUED: 'bg-slate-200 text-slate-700',
  IN_TRANSIT: 'bg-blue-100 text-blue-800',
  RECEIVED: 'bg-indigo-100 text-indigo-800',
  SOLD: 'bg-emerald-100 text-emerald-800',
  RETURNED: 'bg-amber-100 text-amber-800',
  FLAGGED: 'bg-red-100 text-red-800',
  open: 'bg-red-100 text-red-800',
  reviewed: 'bg-slate-200 text-slate-600',
  high: 'bg-red-100 text-red-800',
  medium: 'bg-amber-100 text-amber-800',
  low: 'bg-slate-200 text-slate-600',
  approved: 'bg-emerald-100 text-emerald-800',
  pending: 'bg-amber-100 text-amber-800',
  rejected: 'bg-red-100 text-red-800',
  authorized: 'bg-emerald-100 text-emerald-800',
  unauthorized: 'bg-red-100 text-red-800',
};

export function Badge({ value }: { value: string }) {
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${badgeColors[value] ?? 'bg-slate-200 text-slate-700'}`}>
      {value.replaceAll('_', ' ')}
    </span>
  );
}

/* ---------- copy button with "Copied!" feedback ---------- */
export function CopyButton({ text, label = 'Copy' }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}
      className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs hover:bg-slate-50"
      title="Copy to clipboard"
    >
      {copied ? 'Copied!' : label}
    </button>
  );
}

/* ---------- role-gated control: disabled with tooltip, never hidden ---------- */
export function Gated({ allowed, reason, children }: { allowed: boolean; reason: string; children: React.ReactNode }) {
  if (allowed) return <>{children}</>;
  return (
    <span title={reason} className="inline-block cursor-not-allowed opacity-50">
      <span className="pointer-events-none">{children}</span>
    </span>
  );
}
