import { useEffect, useState } from "react";
import {
  getConfig,
  getModelProfiles,
  getModelRegistry,
  getProviderStatus,
  getProviders,
  updateConfig,
} from "../api/client";
import type { ModelProfile, ModelRegistryItem, ProviderInfo, ProviderMode, ProviderStatus } from "../types";

export default function Settings() {
  const [ollamaUrl, setOllamaUrl] = useState("http://localhost:11434");
  const [model, setModel] = useState("qwen2.5-coder:7b");
  const [codexEnabled, setCodexEnabled] = useState(false);
  const [claudeEnabled, setClaudeEnabled] = useState(false);
  const [defaultMode, setDefaultMode] = useState("offline");
  const [providerMode, setProviderMode] = useState<ProviderMode>("local");
  const [models, setModels] = useState<ModelRegistryItem[]>([]);
  const [profiles, setProfiles] = useState<ModelProfile[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [providerStatus, setProviderStatus] = useState<ProviderStatus[]>([]);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    Promise.all([getConfig(), getModelRegistry(), getModelProfiles(), getProviders(), getProviderStatus()])
      .then(([cfg, nextModels, nextProfiles, nextProviders, nextStatus]) => {
        setOllamaUrl(cfg.ollama?.base_url || "http://localhost:11434");
        setModel(cfg.ollama?.default_model || "qwen2.5-coder:7b");
        setCodexEnabled(cfg.codex?.enabled || false);
        setClaudeEnabled(cfg.claude?.enabled || false);
        setDefaultMode(cfg.default_mode || "offline");
        setProviderMode((cfg.provider_mode as ProviderMode) || "local");
        setModels(nextModels);
        setProfiles(nextProfiles);
        setProviders(nextProviders);
        setProviderStatus(nextStatus);
      })
      .catch(() => {});
  }, []);

  const handleSave = async () => {
    await updateConfig({
      default_mode: defaultMode,
      provider_mode: providerMode,
      ollama_base_url: ollamaUrl,
      ollama_model: model,
      codex_enabled: codexEnabled,
      claude_enabled: claudeEnabled,
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const statusByProvider = Object.fromEntries(providerStatus.map((status) => [status.id, status]));
  const installedModels = models.filter((item) => item.installed);
  const heavyMissingModels = models.filter(
    (item) => item.provider === "local_ollama" && item.enabled && !item.installed,
  );

  return (
    <div className="max-w-5xl space-y-6">
      <h2 className="text-2xl font-bold">Settings</h2>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Section title="Default Run Mode">
          <select
            value={defaultMode}
            onChange={(e) => setDefaultMode(e.target.value)}
            className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none"
          >
            <option value="offline">Offline (Ollama only)</option>
            <option value="hybrid">Hybrid (local-first + cloud)</option>
            <option value="cloud">Cloud (uses external providers)</option>
          </select>
        </Section>

        <Section title="Provider Mode">
          <select
            value={providerMode}
            onChange={(e) => setProviderMode(e.target.value as ProviderMode)}
            className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none"
          >
            <option value="local">Local (Ollama only)</option>
            <option value="hybrid">Hybrid (local-first routing)</option>
            <option value="cloud">Cloud (external allowed when safe)</option>
          </select>
          <p className="mt-2 text-xs text-gray-500">
            Local mode blocks external providers even if their toggles are enabled.
          </p>
        </Section>
      </div>

      <Section title="Ollama">
        <label className="block text-xs text-gray-500 mb-1">Base URL</label>
        <input
          value={ollamaUrl}
          onChange={(e) => setOllamaUrl(e.target.value)}
          className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500 mb-3"
        />
        <label className="block text-xs text-gray-500 mb-1">Default Model</label>
        <input
          value={model}
          onChange={(e) => setModel(e.target.value)}
          className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500"
        />
      </Section>

      <Section title="Cloud Providers">
        <Toggle label="Enable Codex CLI Provider" checked={codexEnabled} onChange={setCodexEnabled} />
        <Toggle label="Enable Claude Code Provider" checked={claudeEnabled} onChange={setClaudeEnabled} />
        <p className="text-xs text-gray-500 mt-2">
          Cloud providers are optional, disabled by default, and still require approvals before any real execution.
        </p>
      </Section>

      <Section title="Provider Status">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {providers.map((provider) => {
            const status = statusByProvider[provider.id];
            return (
              <div key={provider.id} className="rounded border border-gray-800 bg-gray-950 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-medium text-gray-200">{provider.display_name}</h3>
                    <p className="mt-1 text-xs text-gray-500">{provider.id}</p>
                  </div>
                  <Badge tone={provider.enabled ? "emerald" : "gray"}>
                    {provider.enabled ? "enabled" : "disabled"}
                  </Badge>
                </div>
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                  <Badge tone={status?.available ? "emerald" : "yellow"}>
                    {status?.status || "unknown"}
                  </Badge>
                  <Badge tone={provider.local ? "emerald" : "gray"}>{provider.kind}</Badge>
                  {provider.requires_approval && <Badge tone="yellow">approval gated</Badge>}
                </div>
                {status?.warnings?.length > 0 && (
                  <p className="mt-2 text-xs text-yellow-300">{status.warnings[0]}</p>
                )}
              </div>
            );
          })}
        </div>
      </Section>

      <Section title="Model Registry">
        <div className="mb-3 flex flex-wrap gap-2 text-xs">
          <Badge tone="emerald">{installedModels.length} installed</Badge>
          <Badge tone="yellow">{heavyMissingModels.length} local models not installed</Badge>
          <Badge tone="gray">{profiles.length} profiles</Badge>
        </div>
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          {models.map((item) => (
            <div key={item.id} className="rounded border border-gray-800 bg-gray-950 p-3">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <h3 className="truncate text-sm font-medium text-gray-200">{item.display_name}</h3>
                  <p className="mt-1 truncate font-mono text-xs text-gray-500">{item.id}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge tone={item.installed ? "emerald" : "yellow"}>
                    {item.installed ? "installed" : "not installed"}
                  </Badge>
                  <Badge tone={item.enabled ? "emerald" : "gray"}>
                    {item.enabled ? "enabled" : "disabled"}
                  </Badge>
                </div>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-gray-500">
                <Info label="provider" value={item.provider} />
                <Info label="memory" value={`${item.memory_tier}, max ${item.max_parallel}`} />
              </div>
              <p className="mt-2 text-xs text-gray-500">{item.notes}</p>
              {(item.memory_tier === "large" || item.memory_tier === "xlarge") && (
                <p className="mt-2 text-xs text-yellow-300">
                  Heavy local model; router keeps max_parallel={item.max_parallel}.
                </p>
              )}
            </div>
          ))}
        </div>
      </Section>

      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          className="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 rounded text-sm font-medium"
        >
          Save Settings
        </button>
        {saved && <span className="text-emerald-400 text-sm">Saved!</span>}
      </div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded bg-gray-900 px-2 py-1.5">
      <span className="text-gray-600">{label}</span>
      <p className="truncate text-gray-300">{value || "unset"}</p>
    </div>
  );
}

function Badge({ children, tone }: { children: React.ReactNode; tone: "emerald" | "yellow" | "gray" }) {
  const styles: Record<typeof tone, string> = {
    emerald: "bg-emerald-900/40 text-emerald-300",
    yellow: "bg-yellow-900/40 text-yellow-300",
    gray: "bg-gray-800 text-gray-300",
  };
  return <span className={`rounded px-2 py-0.5 text-xs ${styles[tone]}`}>{children}</span>;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-900 rounded border border-gray-800 p-4">
      <h3 className="font-medium mb-3">{title}</h3>
      {children}
    </div>
  );
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-3 py-1 cursor-pointer">
      <div
        onClick={() => onChange(!checked)}
        className={`w-10 h-5 rounded-full relative transition-colors ${
          checked ? "bg-emerald-600" : "bg-gray-700"
        }`}
      >
        <div
          className={`w-4 h-4 rounded-full bg-white absolute top-0.5 transition-transform ${
            checked ? "translate-x-5" : "translate-x-0.5"
          }`}
        />
      </div>
      <span className="text-sm text-gray-300">{label}</span>
    </label>
  );
}
