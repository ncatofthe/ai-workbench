import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getRuns } from "../api/client";
import StatusBadge from "../components/StatusBadge";
import type { Run } from "../types";

export default function Runs() {
  const [runs, setRuns] = useState<Run[]>([]);

  useEffect(() => {
    getRuns().then(setRuns).catch(() => {});
    const interval = setInterval(() => getRuns().then(setRuns).catch(() => {}), 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Runs</h2>
        <Link
          to="/new-task"
          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 rounded text-sm"
        >
          New Task
        </Link>
      </div>

      {runs.length === 0 ? (
        <p className="text-gray-500">No runs yet.</p>
      ) : (
        <div className="bg-gray-900 rounded border border-gray-800 divide-y divide-gray-800">
          {runs.map((r) => (
            <Link
              key={r.id}
              to={`/runs/${r.id}`}
              className="block p-4 hover:bg-gray-800/50 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0 mr-4">
                  <p className="text-sm truncate">{r.prompt}</p>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-xs text-gray-500">{r.id}</span>
                    <span className="text-xs text-gray-500">{r.mode}</span>
                    <span className="text-xs text-gray-500">{r.created_at}</span>
                  </div>
                </div>
                <StatusBadge status={r.status} />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
