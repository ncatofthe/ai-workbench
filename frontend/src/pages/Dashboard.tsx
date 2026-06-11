import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getHealth, getAgents, getRuns } from "../api/client";
import StatusBadge from "../components/StatusBadge";
import type { Run } from "../types";

export default function Dashboard() {
  const [health, setHealth] = useState<any>(null);
  const [agents, setAgents] = useState<any[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);

  useEffect(() => {
    const load = () => {
      getHealth().then(setHealth).catch(() => setHealth({ status: "error", ollama: "disconnected" }));
      getAgents().then(setAgents).catch(() => {});
      getRuns().then(setRuns).catch(() => {});
    };
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  const activeRuns = runs.filter((r) => r.status === "running" || r.status === "pending");

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Dashboard</h2>

      {/* Status cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card
          title="Backend"
          value={health?.status === "ok" ? "Online" : "Offline"}
          color={health?.status === "ok" ? "emerald" : "red"}
        />
        <Card
          title="Ollama"
          value={health?.ollama === "connected" ? "Connected" : "Disconnected"}
          color={health?.ollama === "connected" ? "emerald" : "yellow"}
        />
        <Card title="Agents" value={String(agents.length)} color="blue" />
        <Card title="Active Runs" value={String(activeRuns.length)} color="purple" />
      </div>

      {/* Recent runs */}
      <div>
        <h3 className="text-lg font-semibold mb-3">Recent Runs</h3>
        {runs.length === 0 ? (
          <p className="text-gray-500 text-sm">No runs yet. Create a new task to get started.</p>
        ) : (
          <div className="bg-gray-900 rounded border border-gray-800 divide-y divide-gray-800">
            {runs.slice(0, 5).map((r) => (
              <Link
                key={r.id}
                to={`/runs/${r.id}`}
                className="p-3 flex items-center justify-between hover:bg-gray-800/50 transition-colors"
              >
                <div className="min-w-0 mr-4">
                  <p className="text-sm truncate">{r.prompt}</p>
                  <p className="text-xs text-gray-500 mt-1">{r.created_at}</p>
                </div>
                <StatusBadge status={r.status} />
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Agents */}
      <div>
        <h3 className="text-lg font-semibold mb-3">Agents</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {agents.map((a) => (
            <div key={a.id} className="bg-gray-900 rounded border border-gray-800 p-3">
              <p className="font-medium text-sm">{a.name}</p>
              <p className="text-xs text-gray-500 mt-1">{a.description}</p>
              <p className="text-xs text-emerald-500 mt-2">Provider: {a.provider}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Card({ title, value, color }: { title: string; value: string; color: string }) {
  const bg: Record<string, string> = {
    emerald: "border-emerald-800 bg-emerald-950/30",
    red: "border-red-800 bg-red-950/30",
    yellow: "border-yellow-800 bg-yellow-950/30",
    blue: "border-blue-800 bg-blue-950/30",
    purple: "border-purple-800 bg-purple-950/30",
  };
  return (
    <div className={`rounded border p-4 ${bg[color] ?? bg.blue}`}>
      <p className="text-xs text-gray-400 uppercase tracking-wide">{title}</p>
      <p className="text-xl font-bold mt-1">{value}</p>
    </div>
  );
}
