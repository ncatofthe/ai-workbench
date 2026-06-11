import { NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "Dashboard", icon: "⬡" },
  { to: "/new-task", label: "New Task", icon: "+" },
  { to: "/runs", label: "Runs", icon: "▶" },
  { to: "/agents", label: "Agents", icon: "◉" },
  { to: "/projects", label: "Projects", icon: "□" },
  { to: "/approvals", label: "Approvals", icon: "⚑" },
  { to: "/tools", label: "Tools", icon: "◧" },
  { to: "/settings", label: "Settings", icon: "⚙" },
];

export default function Sidebar() {
  return (
    <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col min-h-screen">
      <div className="p-4 border-b border-gray-800">
        <h1 className="text-lg font-bold text-emerald-400">AI Workbench</h1>
        <p className="text-xs text-gray-500 mt-1">Local Agent Platform</p>
      </div>
      <nav className="flex-1 p-2 space-y-1">
        {links.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            className={({ isActive }) =>
              `flex items-center gap-2 px-3 py-2 rounded text-sm transition-colors ${
                isActive
                  ? "bg-emerald-900/40 text-emerald-300"
                  : "text-gray-400 hover:text-gray-200 hover:bg-gray-800"
              }`
            }
          >
            <span className="w-5 text-center">{l.icon}</span>
            {l.label}
          </NavLink>
        ))}
      </nav>
      <div className="p-4 border-t border-gray-800 text-xs text-gray-600">
        MVP v0.1.0 — offline-first
      </div>
    </aside>
  );
}
