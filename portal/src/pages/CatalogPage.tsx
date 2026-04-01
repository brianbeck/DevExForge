import { useEffect, useState } from "react";
import {
  listTemplates,
  createTemplate,
  deleteTemplate,
  deployFromTemplate,
} from "@/api/catalog";
import type { CatalogTemplate } from "@/api/catalog";
import { listTeams } from "@/api/teams";
import type { Team } from "@/types";

export default function CatalogPage() {
  const [templates, setTemplates] = useState<CatalogTemplate[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<CatalogTemplate | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showDeployForm, setShowDeployForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [createData, setCreateData] = useState({
    name: "",
    description: "",
    category: "",
    chartRepo: "",
    chartName: "",
    chartVersion: "",
    defaultValues: "",
    valuesSchema: "",
  });

  const [deployData, setDeployData] = useState({
    teamSlug: "",
    tier: "dev",
    appName: "",
    values: "",
  });

  async function fetchData() {
    try {
      setLoading(true);
      const [templateList, teamList] = await Promise.all([
        listTemplates(),
        listTeams(),
      ]);
      setTemplates(templateList);
      setTeams(teamList.teams);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load catalog");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchData();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await createTemplate({
        name: createData.name,
        description: createData.description || null,
        category: createData.category || null,
        chartRepo: createData.chartRepo || null,
        chartName: createData.chartName || null,
        chartVersion: createData.chartVersion || null,
        defaultValues: createData.defaultValues
          ? JSON.parse(createData.defaultValues)
          : null,
        valuesSchema: createData.valuesSchema
          ? JSON.parse(createData.valuesSchema)
          : null,
      });
      setShowCreateForm(false);
      setCreateData({
        name: "",
        description: "",
        category: "",
        chartRepo: "",
        chartName: "",
        chartVersion: "",
        defaultValues: "",
        valuesSchema: "",
      });
      await fetchData();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create template"
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this template?")) return;
    try {
      await deleteTemplate(id);
      if (selected?.id === id) setSelected(null);
      await fetchData();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to delete template"
      );
    }
  }

  async function handleDeploy(e: React.FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setSubmitting(true);
    try {
      const result = await deployFromTemplate(
        deployData.teamSlug,
        deployData.tier,
        {
          templateId: selected.id,
          appName: deployData.appName,
          values: deployData.values
            ? JSON.parse(deployData.values)
            : undefined,
        }
      );
      alert(
        `Deployed "${result.applicationName}" to ${result.namespace}`
      );
      setShowDeployForm(false);
      setDeployData({ teamSlug: "", tier: "dev", appName: "", values: "" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to deploy");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="loading-screen">
        <p>Loading catalog...</p>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Service Catalog</h2>
        <button
          className="btn btn-primary"
          onClick={() => {
            setShowCreateForm(!showCreateForm);
            if (showCreateForm) setSelected(null);
          }}
        >
          {showCreateForm ? "Cancel" : "Create Template"}
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {showCreateForm && (
        <form className="card form-card" onSubmit={handleCreate}>
          <h3>New Template</h3>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="tpl-name">Name</label>
              <input
                id="tpl-name"
                type="text"
                required
                value={createData.name}
                onChange={(e) =>
                  setCreateData({ ...createData, name: e.target.value })
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="tpl-category">Category</label>
              <input
                id="tpl-category"
                type="text"
                placeholder="web, api, worker..."
                value={createData.category}
                onChange={(e) =>
                  setCreateData({ ...createData, category: e.target.value })
                }
              />
            </div>
          </div>
          <div className="form-group">
            <label htmlFor="tpl-description">Description</label>
            <input
              id="tpl-description"
              type="text"
              value={createData.description}
              onChange={(e) =>
                setCreateData({ ...createData, description: e.target.value })
              }
            />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="tpl-chartRepo">Chart Repo</label>
              <input
                id="tpl-chartRepo"
                type="text"
                value={createData.chartRepo}
                onChange={(e) =>
                  setCreateData({ ...createData, chartRepo: e.target.value })
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="tpl-chartName">Chart Name</label>
              <input
                id="tpl-chartName"
                type="text"
                value={createData.chartName}
                onChange={(e) =>
                  setCreateData({ ...createData, chartName: e.target.value })
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="tpl-chartVersion">Chart Version</label>
              <input
                id="tpl-chartVersion"
                type="text"
                value={createData.chartVersion}
                onChange={(e) =>
                  setCreateData({
                    ...createData,
                    chartVersion: e.target.value,
                  })
                }
              />
            </div>
          </div>
          <div className="form-group">
            <label htmlFor="tpl-defaultValues">Default Values (JSON)</label>
            <textarea
              id="tpl-defaultValues"
              rows={3}
              style={{
                padding: "8px 12px",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-sm)",
                fontFamily: "monospace",
                fontSize: "13px",
              }}
              value={createData.defaultValues}
              onChange={(e) =>
                setCreateData({ ...createData, defaultValues: e.target.value })
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="tpl-valuesSchema">Values Schema (JSON)</label>
            <textarea
              id="tpl-valuesSchema"
              rows={3}
              style={{
                padding: "8px 12px",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-sm)",
                fontFamily: "monospace",
                fontSize: "13px",
              }}
              value={createData.valuesSchema}
              onChange={(e) =>
                setCreateData({ ...createData, valuesSchema: e.target.value })
              }
            />
          </div>
          <button
            className="btn btn-primary"
            type="submit"
            disabled={submitting}
          >
            {submitting ? "Creating..." : "Create"}
          </button>
        </form>
      )}

      {templates.length === 0 && !showCreateForm ? (
        <div className="empty-state">
          <p>No templates in the catalog yet.</p>
        </div>
      ) : (
        <div className="catalog-grid">
          {templates.map((tpl) => (
            <div
              key={tpl.id}
              className={`template-card${selected?.id === tpl.id ? " active" : ""}`}
              onClick={() => {
                setSelected(tpl);
                setShowDeployForm(false);
              }}
            >
              {tpl.category && <span className="category">{tpl.category}</span>}
              <h3>{tpl.name}</h3>
              {tpl.description && (
                <p className="card-description">{tpl.description}</p>
              )}
              <div className="card-meta">
                {tpl.chartName && <span>{tpl.chartName}</span>}
                {tpl.chartVersion && <span>v{tpl.chartVersion}</span>}
              </div>
              <div style={{ marginTop: "0.75rem" }}>
                <button
                  className="btn btn-danger btn-sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(tpl.id);
                  }}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {selected && (
        <div className="template-detail">
          <div className="card-header-row">
            <h3>{selected.name}</h3>
            <div className="btn-group">
              <button
                className="btn btn-primary btn-sm"
                onClick={() => setShowDeployForm(!showDeployForm)}
              >
                {showDeployForm ? "Cancel" : "Deploy"}
              </button>
              <button
                className="btn btn-sm"
                onClick={() => {
                  setSelected(null);
                  setShowDeployForm(false);
                }}
              >
                Close
              </button>
            </div>
          </div>

          <div className="detail-grid">
            <dt>Category</dt>
            <dd>{selected.category || "None"}</dd>
            <dt>Chart Repo</dt>
            <dd className="text-mono">{selected.chartRepo || "N/A"}</dd>
            <dt>Chart Name</dt>
            <dd className="text-mono">{selected.chartName || "N/A"}</dd>
            <dt>Chart Version</dt>
            <dd>{selected.chartVersion || "N/A"}</dd>
            <dt>Created</dt>
            <dd>{new Date(selected.createdAt).toLocaleString()}</dd>
          </div>

          {selected.defaultValues && (
            <div style={{ marginTop: "1rem" }}>
              <h4>Default Values</h4>
              <pre
                style={{
                  background: "#1e1e1e",
                  color: "#d4d4d4",
                  padding: "1rem",
                  borderRadius: "4px",
                  overflow: "auto",
                  fontSize: "0.85rem",
                }}
              >
                {JSON.stringify(selected.defaultValues, null, 2)}
              </pre>
            </div>
          )}

          {showDeployForm && (
            <form
              className="deploy-form"
              onSubmit={handleDeploy}
              style={{ marginTop: "1rem" }}
            >
              <h4>Deploy from &ldquo;{selected.name}&rdquo;</h4>
              <div className="form-group">
                <label htmlFor="deploy-team">Team</label>
                <select
                  id="deploy-team"
                  required
                  value={deployData.teamSlug}
                  onChange={(e) =>
                    setDeployData({ ...deployData, teamSlug: e.target.value })
                  }
                >
                  <option value="">Select a team...</option>
                  {teams.map((t) => (
                    <option key={t.slug} value={t.slug}>
                      {t.displayName} ({t.slug})
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label htmlFor="deploy-tier">Environment Tier</label>
                <select
                  id="deploy-tier"
                  required
                  value={deployData.tier}
                  onChange={(e) =>
                    setDeployData({ ...deployData, tier: e.target.value })
                  }
                >
                  <option value="dev">dev</option>
                  <option value="staging">staging</option>
                  <option value="prod">prod</option>
                </select>
              </div>
              <div className="form-group">
                <label htmlFor="deploy-appName">Application Name</label>
                <input
                  id="deploy-appName"
                  type="text"
                  required
                  placeholder="my-app"
                  value={deployData.appName}
                  onChange={(e) =>
                    setDeployData({ ...deployData, appName: e.target.value })
                  }
                />
              </div>
              <div className="form-group">
                <label htmlFor="deploy-values">
                  Values Override (JSON, optional)
                </label>
                <textarea
                  id="deploy-values"
                  rows={4}
                  style={{
                    padding: "8px 12px",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-sm)",
                    fontFamily: "monospace",
                    fontSize: "13px",
                  }}
                  value={deployData.values}
                  onChange={(e) =>
                    setDeployData({ ...deployData, values: e.target.value })
                  }
                />
              </div>
              <button
                className="btn btn-primary"
                type="submit"
                disabled={submitting}
              >
                {submitting ? "Deploying..." : "Deploy"}
              </button>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
