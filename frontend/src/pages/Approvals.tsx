import { useEffect, useState } from "react";
import { getApprovals, approveRequest, rejectRequest } from "../api/client";
import StatusBadge from "../components/StatusBadge";
import type { ApprovalRequest } from "../types";

export default function Approvals() {
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [notice, setNotice] = useState("");

  const reload = () => getApprovals().then(setApprovals).catch(() => {});

  useEffect(() => {
    reload();
    const interval = setInterval(reload, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleApprove = async (id: string) => {
    const result = await approveRequest(id);
    if (result.execution) {
      setNotice(
        `Command ${result.execution.status} with exit code ${result.execution.returncode}. Report: ${result.execution.report_path}`,
      );
    } else if (result.already_resolved) {
      setNotice("Approval was already resolved.");
    } else {
      setNotice("Approval recorded.");
    }
    reload();
  };

  const handleReject = async (id: string) => {
    await rejectRequest(id);
    reload();
  };

  const pending = approvals.filter((a) => a.status === "pending");
  const resolved = approvals.filter((a) => a.status !== "pending");

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Approvals</h2>

      {notice && (
        <div className="rounded border border-blue-800/60 bg-blue-950/30 p-3 text-sm text-blue-100">
          {notice}
        </div>
      )}

      {pending.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold mb-3 text-yellow-400">Pending Approval</h3>
          <div className="space-y-3">
            {pending.map((a) => (
              <div key={a.id} className="bg-yellow-950/20 border border-yellow-800/50 rounded p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-sm">{a.action}</span>
                  <StatusBadge status={a.status} />
                </div>
                {a.command && (
                  <pre className="bg-gray-900 rounded p-2 text-xs font-mono text-gray-300 mb-2">
                    {a.command}
                  </pre>
                )}
                {a.description && <p className="text-sm text-gray-400 mb-3">{a.description}</p>}
                <div className="flex gap-2">
                  <button
                    onClick={() => handleApprove(a.id)}
                    className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 rounded text-sm"
                  >
                    {a.run_id.startsWith("project:") && a.command ? "Approve & Run" : "Approve"}
                  </button>
                  <button
                    onClick={() => handleReject(a.id)}
                    className="px-4 py-1.5 bg-red-800 hover:bg-red-700 rounded text-sm"
                  >
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {pending.length === 0 && (
        <p className="text-gray-500 text-sm">No pending approvals.</p>
      )}

      {resolved.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-400 mb-2">History</h3>
          <div className="bg-gray-900 rounded border border-gray-800 divide-y divide-gray-800">
            {resolved.map((a) => (
              <div key={a.id} className="p-3 flex items-center justify-between">
                <div>
                  <p className="text-sm">{a.action}</p>
                  <p className="text-xs text-gray-500">{a.created_at}</p>
                </div>
                <StatusBadge status={a.status} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
