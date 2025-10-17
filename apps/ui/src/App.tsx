// src/App.tsx
import { useState } from 'react';
import { useApi } from '@/hooks/useApi';

type StatusRes = { status: string };
type FlowsRes = { nodes: Array<{ id: string; label: string }>; edges: Array<{ source: string; target: string; weight: number }> };
type AskRes = { sql?: string; message?: string; query?: string };
type AnomalyRes = { score: number; is_anomaly: boolean; message: string; severity?: string };

export default function App() {
  // Demo amaçlı tenant/role alanları:
  const [tenantId, setTenantId] = useState('dev');
  const [role, setRole] = useState('admin'); // admin/analyst gibi
  const [address, setAddress] = useState('0x1234567890abcdef1234567890abcdef12345678');
  const [nlQuery, setNlQuery] = useState('Top suspicious transfers last 24h');

  const api = useApi({ tenantId, role /* , token: '...JWT...'  */ });

  const [out, setOut] = useState<unknown>(null);
  const [err, setErr] = useState<string | null>(null);

  const run = async (fn: () => Promise<unknown>) => {
    setErr(null);
    setOut(null);
    try {
      const data = await fn();
      setOut(data);
    } catch (e: any) {
      setErr(e?.message ?? String(e));
    }
  };

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-4">
      <h1 className="text-2xl font-bold">Blockchain Analytics Dashboard</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="p-3 border rounded">
          <label className="text-sm block">Tenant Id</label>
          <input className="w-full border rounded p-2" value={tenantId} onChange={e => setTenantId(e.target.value)} />
        </div>
        <div className="p-3 border rounded">
          <label className="text-sm block">Role</label>
          <input className="w-full border rounded p-2" value={role} onChange={e => setRole(e.target.value)} />
        </div>
        <div className="p-3 border rounded">
          <label className="text-sm block">Address</label>
          <input className="w-full border rounded p-2" value={address} onChange={e => setAddress(e.target.value)} />
        </div>
      </div>

      <div className="p-3 border rounded">
        <label className="text-sm block">NL Query</label>
        <input className="w-full border rounded p-2" value={nlQuery} onChange={e => setNlQuery(e.target.value)} />
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          className="px-3 py-2 rounded bg-blue-600 text-white"
          onClick={() => run<StatusRes>(() => api.get<StatusRes>('/status'))}
        >
          Status
        </button>

        <button
          className="px-3 py-2 rounded bg-indigo-600 text-white"
          onClick={() => run<FlowsRes>(() => api.get<FlowsRes>(`/flows?address=${encodeURIComponent(address)}`))}
        >
          Flows
        </button>

        <button
          className="px-3 py-2 rounded bg-emerald-600 text-white"
          onClick={() => run<AskRes>(() => api.post<AskRes>('/ask', { query: nlQuery }))}
        >
          Ask (NL → SQL)
        </button>

        <button
          className="px-3 py-2 rounded bg-orange-600 text-white"
          onClick={() =>
            run<AnomalyRes>(() =>
              api.post<AnomalyRes>('/anomaly', { values: [1, 2, 3, 100, 2, 3], threshold: 3.0 })
            )
          }
        >
          Anomaly
        </button>
      </div>

      {err && (
        <pre className="bg-rose-50 text-rose-700 p-3 rounded whitespace-pre-wrap">
          Error: {err}
        </pre>
      )}

      {out && (
        <pre className="bg-gray-900 text-green-200 p-3 rounded overflow-auto">
          {JSON.stringify(out, null, 2)}
        </pre>
      )}
    </div>
  );
}
