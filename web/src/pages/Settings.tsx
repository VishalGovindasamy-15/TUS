import { useEffect, useState } from 'react';
import { extractError } from '../api/client';
import { useNotifSettings, useSaveNotifSettings } from '../api/hooks';
import { useToast } from '../components/Toast';
import { ErrorState, SkeletonRows } from '../components/ui';

const CHANNELS = ['push', 'sms', 'whatsapp', 'email'];

export default function Settings() {
  const settings = useNotifSettings();
  const save = useSaveNotifSettings();
  const { toast } = useToast();
  const [channels, setChannels] = useState<string[]>([]);
  const [language, setLanguage] = useState('en');

  useEffect(() => {
    if (settings.data) {
      setChannels(settings.data.channels);
      setLanguage(settings.data.language);
    }
  }, [settings.data]);

  if (settings.isLoading) return <SkeletonRows rows={3} />;
  if (settings.isError) return <ErrorState message={extractError(settings.error)} onRetry={() => settings.refetch()} />;

  const toggle = (c: string) =>
    setChannels((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));

  const submit = async () => {
    try {
      await save.mutateAsync({ channels, language });
      toast('success', 'Notification settings saved');
    } catch (e) {
      toast('error', extractError(e));
    }
  };

  return (
    <div className="max-w-lg space-y-4">
      <h1 className="text-xl font-bold">Notification Settings</h1>
      <div className="rounded-xl bg-white p-4 shadow-sm">
        <p className="mb-2 text-sm font-medium text-slate-600">Channels</p>
        <div className="flex flex-wrap gap-3">
          {CHANNELS.map((c) => (
            <label key={c} className="flex items-center gap-1.5 text-sm capitalize">
              <input type="checkbox" checked={channels.includes(c)} onChange={() => toggle(c)} />
              {c}
            </label>
          ))}
        </div>
        <p className="mb-2 mt-4 text-sm font-medium text-slate-600">Language</p>
        <select value={language} onChange={(e) => setLanguage(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
          <option value="en">English</option>
          <option value="hi">Hindi</option>
          <option value="ta">Tamil</option>
        </select>
        <button onClick={submit} disabled={save.isPending} className="mt-4 w-full rounded-lg bg-brand-600 py-2 text-sm text-white disabled:opacity-50">
          {save.isPending ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  );
}
