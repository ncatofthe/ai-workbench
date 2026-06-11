import { useEffect, useMemo, useState } from "react";
import { createProject, getProjects, updateProject } from "../api/client";
import type { Project, ProjectProfileInput } from "../types";

type FormState = {
  name: string;
  path: string;
  description: string;
  stack: string;
  package_manager: string;
  test_command: string;
  build_command: string;
  safe_commands: string;
  blocked_commands: string;
  ignore_paths: string;
};

const emptyForm: FormState = {
  name: "",
  path: "",
  description: "",
  stack: "",
  package_manager: "",
  test_command: "",
  build_command: "",
  safe_commands: "",
  blocked_commands: "",
  ignore_paths: "",
};

export default function Projects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [editingId, setEditingId] = useState<string>("");
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const editingProject = useMemo(
    () => projects.find((project) => project.id === editingId) || null,
    [editingId, projects],
  );

  const loadProjects = async () => {
    setError("");
    try {
      setProjects(await getProjects());
    } catch (e: any) {
      setError(e.message);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  const updateField = (field: keyof FormState, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const openCreate = () => {
    setEditingId("");
    setForm(emptyForm);
    setShowForm(true);
    setError("");
  };

  const openEdit = (project: Project) => {
    setEditingId(project.id);
    setForm(projectToForm(project));
    setShowForm(true);
    setError("");
  };

  const closeForm = () => {
    setShowForm(false);
    setEditingId("");
    setForm(emptyForm);
  };

  const handleSave = async () => {
    if (!form.name.trim() || !form.path.trim()) {
      setError("Project name and absolute path are required.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const payload = formToPayload(form);
      if (editingId) {
        await updateProject(editingId, payload);
      } else {
        await createProject(payload);
      }
      await loadProjects();
      closeForm();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold">Projects</h2>
          <p className="mt-1 text-sm text-gray-500">Execution profiles for external repositories.</p>
        </div>
        <button
          onClick={openCreate}
          className="w-full rounded bg-emerald-600 px-4 py-2 text-sm hover:bg-emerald-500 sm:w-auto"
        >
          New Project
        </button>
      </div>

      {error && (
        <div className="rounded border border-red-800 bg-red-950/30 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {showForm && (
        <section className="rounded border border-gray-800 bg-gray-900 p-4">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h3 className="font-semibold">{editingProject ? "Edit Project" : "New Project"}</h3>
              <p className="mt-1 text-xs text-gray-500">
                Commands run only when they exactly match safe commands.
              </p>
            </div>
            <button onClick={closeForm} className="rounded bg-gray-800 px-3 py-1.5 text-sm hover:bg-gray-700">
              Cancel
            </button>
          </div>

          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <TextField label="Name" value={form.name} onChange={(value) => updateField("name", value)} />
            <TextField label="Absolute Path" value={form.path} onChange={(value) => updateField("path", value)} />
            <TextField label="Stack" value={form.stack} onChange={(value) => updateField("stack", value)} />
            <TextField
              label="Package Manager"
              value={form.package_manager}
              onChange={(value) => updateField("package_manager", value)}
            />
            <TextField
              label="Test Command"
              value={form.test_command}
              onChange={(value) => updateField("test_command", value)}
            />
            <TextField
              label="Build Command"
              value={form.build_command}
              onChange={(value) => updateField("build_command", value)}
            />
            <TextArea
              label="Description"
              value={form.description}
              onChange={(value) => updateField("description", value)}
            />
            <TextArea
              label="Safe Commands"
              value={form.safe_commands}
              onChange={(value) => updateField("safe_commands", value)}
            />
            <TextArea
              label="Blocked Commands"
              value={form.blocked_commands}
              onChange={(value) => updateField("blocked_commands", value)}
            />
            <TextArea
              label="Ignore Paths"
              value={form.ignore_paths}
              onChange={(value) => updateField("ignore_paths", value)}
            />
          </div>

          <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center">
            <button
              onClick={handleSave}
              disabled={loading}
              className="rounded bg-emerald-600 px-5 py-2 text-sm font-medium hover:bg-emerald-500 disabled:bg-gray-700 disabled:text-gray-500"
            >
              {loading ? "Saving..." : editingProject ? "Save Changes" : "Create Project"}
            </button>
            <p className="text-xs text-gray-500">Use one item per line for safe, blocked, and ignored entries.</p>
          </div>
        </section>
      )}

      {projects.length === 0 ? (
        <div className="rounded border border-gray-800 bg-gray-900 p-4 text-sm text-gray-500">
          No projects yet. Create a profile before starting a task.
        </div>
      ) : (
        <div className="divide-y divide-gray-800 rounded border border-gray-800 bg-gray-900">
          {projects.map((project) => (
            <article key={project.id} className="p-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-medium">{project.name}</h3>
                    {project.stack && <Badge>{project.stack}</Badge>}
                    {project.package_manager && <Badge>{project.package_manager}</Badge>}
                  </div>
                  <p className="mt-1 truncate font-mono text-xs text-gray-500">{project.path || "No path configured"}</p>
                  {project.description && <p className="mt-2 text-sm text-gray-400">{project.description}</p>}
                </div>
                <button
                  onClick={() => openEdit(project)}
                  className="rounded bg-gray-800 px-3 py-1.5 text-sm hover:bg-gray-700"
                >
                  Edit
                </button>
              </div>

              <div className="mt-4 grid grid-cols-1 gap-2 text-xs sm:grid-cols-2 lg:grid-cols-4">
                <Completeness label="Path" ok={Boolean(project.path)} />
                <Completeness label="Tests" ok={Boolean(project.test_command)} />
                <Completeness label="Build" ok={Boolean(project.build_command)} />
                <Completeness label="Safe Commands" ok={project.safe_commands.length > 0} />
              </div>

              <div className="mt-4 grid grid-cols-1 gap-3 text-xs text-gray-500 lg:grid-cols-2">
                <CommandLine label="Test" value={project.test_command} />
                <CommandLine label="Build" value={project.build_command} />
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function projectToForm(project: Project): FormState {
  return {
    name: project.name,
    path: project.path,
    description: project.description,
    stack: project.stack,
    package_manager: project.package_manager,
    test_command: project.test_command,
    build_command: project.build_command,
    safe_commands: project.safe_commands.join("\n"),
    blocked_commands: project.blocked_commands.join("\n"),
    ignore_paths: project.ignore_paths.join("\n"),
  };
}

function formToPayload(form: FormState): ProjectProfileInput {
  return {
    name: form.name.trim(),
    path: form.path.trim(),
    description: form.description.trim(),
    stack: form.stack.trim(),
    package_manager: form.package_manager.trim(),
    test_command: form.test_command.trim(),
    build_command: form.build_command.trim(),
    safe_commands: linesToList(form.safe_commands),
    blocked_commands: linesToList(form.blocked_commands),
    ignore_paths: linesToList(form.ignore_paths),
  };
}

function linesToList(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-gray-500">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none"
      />
    </label>
  );
}

function TextArea({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-gray-500">{label}</span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={4}
        className="w-full resize-y rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none"
      />
    </label>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return <span className="rounded bg-emerald-950 px-2 py-0.5 text-xs text-emerald-300">{children}</span>;
}

function Completeness({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className={`rounded border px-3 py-2 ${ok ? "border-emerald-900 bg-emerald-950/20" : "border-yellow-900 bg-yellow-950/20"}`}>
      <span className={ok ? "text-emerald-300" : "text-yellow-300"}>{ok ? "configured" : "missing"}</span>
      <span className="ml-2 text-gray-400">{label}</span>
    </div>
  );
}

function CommandLine({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-gray-600">{label}</span>
      <p className="mt-1 truncate rounded bg-gray-950 px-2 py-1 font-mono text-gray-400">{value || "(not configured)"}</p>
    </div>
  );
}
