import { useEffect, useState } from "react";
import { getAgentRegistry, getModelProfiles, getModelRegistry } from "../api/client";
import type { AgentInfo, ModelProfile, ModelRegistryItem } from "../types";

export default function Agents() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [profiles, setProfiles] = useState<ModelProfile[]>([]);
  const [models, setModels] = useState<ModelRegistryItem[]>([]);
  const [category, setCategory] = useState("all");

  useEffect(() => {
    Promise.all([getAgentRegistry(), getModelProfiles(), getModelRegistry()])
      .then(([nextAgents, nextProfiles, nextModels]) => {
        setAgents(nextAgents);
        setProfiles(nextProfiles);
        setModels(nextModels);
      })
      .catch(() => {});
  }, []);

  const categories = ["all", ...Array.from(new Set(agents.map((agent) => agent.category))).sort()];
  const visibleAgents = category === "all" ? agents : agents.filter((agent) => agent.category === category);
  const profileById = Object.fromEntries(profiles.map((profile) => [profile.id, profile]));
  const modelById = Object.fromEntries(models.map((model) => [model.id, model]));

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold">Agent Library</h2>
        <p className="mt-1 text-sm text-gray-500">
          Available templates stay local-first. Runs activate only the agents selected by the orchestrator.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {categories.map((item) => (
          <button
            key={item}
            onClick={() => setCategory(item)}
            className={`rounded px-3 py-1.5 text-sm ${
              category === item
                ? "bg-emerald-900/40 text-emerald-300"
                : "bg-gray-900 text-gray-400 hover:bg-gray-800"
            }`}
          >
            {item === "all" ? "All" : item}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {visibleAgents.map((agent) => (
          <article key={agent.id} className="rounded border border-gray-800 bg-gray-900 p-4">
            <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <h3 className="font-medium">{agent.name}</h3>
                <p className="mt-1 text-xs font-mono text-gray-500">{agent.id}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge tone="emerald">{agent.provider}</Badge>
                <Badge tone={agent.risk_level === "high" ? "red" : agent.risk_level === "medium" ? "yellow" : "gray"}>
                  {agent.risk_level}
                </Badge>
              </div>
            </div>

            <p className="text-sm text-gray-400">{agent.description}</p>

            <div className="mt-4 grid grid-cols-1 gap-2 text-xs text-gray-500 sm:grid-cols-3">
              <Info label="category" value={agent.category} />
              <Info label="role" value={agent.role} />
              <Info label="model profile" value={agent.model_profile} />
            </div>

            <ModelProfileSummary
              profile={profileById[agent.model_profile]}
              model={profileById[agent.model_profile] ? modelById[profileById[agent.model_profile].primary_model] : undefined}
            />

            <div className="mt-4 flex flex-wrap gap-2">
              {agent.skills.slice(0, 8).map((skill) => (
                <span key={skill} className="rounded bg-gray-950 px-2 py-1 text-xs text-gray-400">
                  {skill}
                </span>
              ))}
            </div>

            <div className="mt-4 grid grid-cols-1 gap-2 text-xs text-gray-500 sm:grid-cols-2">
              <Capability label="edit files" enabled={agent.can_edit_files} />
              <Capability label="run commands" enabled={agent.can_run_commands} />
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function ModelProfileSummary({
  profile,
  model,
}: {
  profile?: ModelProfile;
  model?: ModelRegistryItem;
}) {
  if (!profile) {
    return (
      <div className="mt-4 rounded border border-yellow-900 bg-yellow-950/20 px-3 py-2 text-xs text-yellow-300">
        Model profile is not registered.
      </div>
    );
  }
  const warning = model && (!model.installed || model.memory_tier === "large" || model.memory_tier === "xlarge");
  return (
    <div className="mt-4 rounded border border-gray-800 bg-gray-950 px-3 py-2 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-gray-500">recommended</span>
        <span className="font-mono text-gray-200">{profile.primary_model}</span>
        <span className="text-gray-600">via</span>
        <span className="text-gray-300">{profile.preferred_provider}</span>
        {model && (
          <span className={model.installed ? "text-emerald-300" : "text-yellow-300"}>
            {model.installed ? "installed" : "not installed"}
          </span>
        )}
      </div>
      <p className="mt-1 text-gray-500">{profile.description}</p>
      {warning && model && (
        <p className="mt-1 text-yellow-300">
          {model.memory_tier} model, max_parallel={model.max_parallel}
        </p>
      )}
    </div>
  );
}

function Badge({ children, tone }: { children: React.ReactNode; tone: "emerald" | "yellow" | "red" | "gray" }) {
  const styles: Record<typeof tone, string> = {
    emerald: "bg-emerald-900/40 text-emerald-300",
    yellow: "bg-yellow-900/40 text-yellow-300",
    red: "bg-red-900/40 text-red-300",
    gray: "bg-gray-800 text-gray-300",
  };
  return <span className={`rounded px-2 py-0.5 text-xs ${styles[tone]}`}>{children}</span>;
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded bg-gray-950 px-2 py-1.5">
      <span className="text-gray-600">{label}</span>
      <p className="truncate text-gray-300">{value || "unset"}</p>
    </div>
  );
}

function Capability({ label, enabled }: { label: string; enabled: boolean }) {
  return (
    <div className={`rounded border px-2 py-1.5 ${enabled ? "border-yellow-900 bg-yellow-950/20" : "border-gray-800 bg-gray-950"}`}>
      <span className={enabled ? "text-yellow-300" : "text-gray-500"}>{enabled ? "allowed by template" : "disabled by default"}</span>
      <span className="ml-2 text-gray-400">{label}</span>
    </div>
  );
}
