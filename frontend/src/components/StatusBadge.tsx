const colors: Record<string, string> = {
  pending: "bg-yellow-900 text-yellow-300",
  running: "bg-blue-900 text-blue-300",
  waiting_approval: "bg-orange-900 text-orange-300",
  completed: "bg-emerald-900 text-emerald-300",
  failed: "bg-red-900 text-red-300",
  stopped: "bg-gray-700 text-gray-300",
  approved: "bg-emerald-900 text-emerald-300",
  rejected: "bg-red-900 text-red-300",
};

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-medium ${colors[status] ?? "bg-gray-700 text-gray-300"}`}
    >
      {status}
    </span>
  );
}
