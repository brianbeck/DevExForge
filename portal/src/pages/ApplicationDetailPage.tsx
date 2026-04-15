import { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  getApplication,
  deleteApplication,
  deployApplication,
  refreshApplication,
  updateApplication,
  getHistory,
} from "@/api/applications";
import type {
  ApplicationDetail,
  ApplicationDeployRequest,
  ApplicationDeployment,
  DeploymentHistory,
  ApplicationUpdate,
} from "@/api/applications";
import { healthBadgeClass } from "./ApplicationsPage";

const TIERS = ["dev", "staging", "production"] as const;
type Tier = (typeof TIERS)[number];

export default function ApplicationDetailPage() {
  const { slug, name } = useParams<{ slug: string; name: string }>();
  const navigate = useNavigate();
  const [app, setApp] = useState<ApplicationDetail | null>(null);
  const [history, setHistory] = useState<DeploymentHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deployTier, setDeployTier] = useState<Tier | null>(null);
  const [deploying, setDeploying] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editData, setEditData] = useState<ApplicationUpdate>({});
  const [deployForm, setDeployForm] = useState({
    imageTag: "",
    chartVersion: "",
    gitSha: "",
    valueOverrides: "",
    strategy: "" as "" | "rolling" | "bluegreen" | "canary",
  });

  const fetchData = useCallback(async () => {
    if (!slug || !name) return;
    try {
      setLoading(true);
      const [appData, histData] = await Promise.all([
        getApplication(slug, name),
        getHistory(slug, name).catch(() => ({ events: [], total: 0 })),
      ]);
      setApp(appData);
      setHistory(histData);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load application"
      );
    } finally {
      setLoading(false);
    }
  }, [slug, name]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function handleDelete() {
    if (!slug || !name) return;
    if (!confirm(`Delete application "${name}"? This cannot be undone.`)) {
      return;
    }
    try {
      await deleteApplication(slug, name);
      navigate(`/teams/${slug}/applications`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete");
    }
  }

  async function handleRefresh() {
    if (!slug || !name) return;
    try {
      const updated = await refreshApplication(slug, name);
      setApp(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh");
    }
  }

  async function handleDeploy(e: React.FormEvent) {
    e.preventDefault();
    if (!slug || !name || !deployTier) return;
    setDeploying(true);
    try {
      const payload: ApplicationDeployRequest = { tier: deployTier };
      if (deployForm.imageTag) payload.imageTag = deployForm.imageTag;
      if (deployForm.chartVersion)
        payload.chartVersion = deployForm.chartVersion;
      if (deployForm.gitSha) payload.gitSha = deployForm.gitSha;
      if (deployForm.strategy) payload.strategy = deployForm.strategy;
      if (deployForm.valueOverrides) {
        payload.valueOverrides = JSON.parse(deployForm.valueOverrides);
      }
      await deployApplication(slug, name, payload);
      setDeployTier(null);
      setDeployForm({
        imageTag: "",
        chartVersion: "",
        gitSha: "",
        valueOverrides: "",
        strategy: "",
      });
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to deploy");
    } finally {
      setDeploying(false);
    }
  }

  async function handleEditSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!slug || !name) return;
    try {
      await updateApplication(slug, name, editData);
      setEditing(false);
      setEditData({});
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update");
    }
  }

  if (loading) {
    return (
      <div className="loading-screen">
        <p>Loading application...</p>
      </div>
    );
  }

  if (error || !app) {
    return (
      <div className="page">
        <div className="alert alert-error">
          {error || "Application not found"}
        </div>
      </div>
    );
  }

  const deploymentsByTier: Record<string, ApplicationDeployment | undefined> =
    {};
  for (const d of app.deployments) {
    deploymentsByTier[d.environmentTier] = d;
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>{app.displayName}</h2>
        <div className="btn-group">
          <button className="btn" onClick={handleRefresh}>
            Refresh
          </button>
          <button
            className="btn"
            onClick={() => {
              setEditing(!editing);
              setEditData({
                displayName: app.displayName,
                description: app.description || "",
                repoUrl: app.repoUrl || "",
                chartPath: app.chartPath || "",
                ownerEmail: app.ownerEmail,
                defaultStrategy: app.defaultStrategy,
              });
            }}
          >
            {editing ? "Cancel Edit" : "Edit"}
          </button>
          <button className="btn btn-danger" onClick={handleDelete}>
            Delete
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {editing && (
        <form className="card form-card" onSubmit={handleEditSubmit}>
          <h4>Edit Application</h4>
          <div className="form-group">
            <label>Display Name</label>
            <input
              type="text"
              value={editData.displayName || ""}
              onChange={(e) =>
                setEditData({ ...editData, displayName: e.target.value })
              }
            />
          </div>
          <div className="form-group">
            <label>Description</label>
            <input
              type="text"
              value={editData.description || ""}
              onChange={(e) =>
                setEditData({ ...editData, description: e.target.value })
              }
            />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Repo URL</label>
              <input
                type="text"
                value={editData.repoUrl || ""}
                onChange={(e) =>
                  setEditData({ ...editData, repoUrl: e.target.value })
                }
              />
            </div>
            <div className="form-group">
              <label>Chart Path</label>
              <input
                type="text"
                value={editData.chartPath || ""}
                onChange={(e) =>
                  setEditData({ ...editData, chartPath: e.target.value })
                }
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Owner Email</label>
              <input
                type="email"
                value={editData.ownerEmail || ""}
                onChange={(e) =>
                  setEditData({ ...editData, ownerEmail: e.target.value })
                }
              />
            </div>
            <div className="form-group">
              <label>Default Strategy</label>
              <select
                value={editData.defaultStrategy || "rolling"}
                onChange={(e) =>
                  setEditData({
                    ...editData,
                    defaultStrategy: e.target.value as
                      | "rolling"
                      | "bluegreen"
                      | "canary",
                  })
                }
              >
                <option value="rolling">rolling</option>
                <option value="bluegreen">bluegreen</option>
                <option value="canary">canary</option>
              </select>
            </div>
          </div>
          <button className="btn btn-primary" type="submit">
            Save Changes
          </button>
        </form>
      )}

      <div className="detail-section">
        <h3>Details</h3>
        <dl className="detail-grid">
          <dt>Name</dt>
          <dd className="text-mono">{app.name}</dd>
          <dt>Description</dt>
          <dd>{app.description || "No description"}</dd>
          <dt>Owner</dt>
          <dd>{app.ownerEmail}</dd>
          <dt>Repo URL</dt>
          <dd>
            {app.repoUrl ? (
              <a href={app.repoUrl} target="_blank" rel="noopener noreferrer">
                {app.repoUrl}
              </a>
            ) : (
              "Not set"
            )}
          </dd>
          <dt>Chart Path</dt>
          <dd className="text-mono">{app.chartPath || "Not set"}</dd>
          <dt>Chart Repo</dt>
          <dd className="text-mono">{app.chartRepoUrl || "Not set"}</dd>
          <dt>Strategy</dt>
          <dd>{app.defaultStrategy}</dd>
        </dl>
      </div>

      <div className="detail-section">
        <h3>Deployments</h3>
        <div className="deployment-cards">
          {TIERS.map((tier) => {
            const d = deploymentsByTier[tier];
            return (
              <div key={tier} className="deployment-card">
                <div className="deployment-card-header">
                  <h4>{tier}</h4>
                  <button
                    className="btn btn-sm btn-primary"
                    onClick={() =>
                      setDeployTier(deployTier === tier ? null : tier)
                    }
                  >
                    {deployTier === tier ? "Cancel" : "Deploy"}
                  </button>
                </div>
                {d ? (
                  <>
                    <dl className="deployment-meta">
                      <dt>Version</dt>
                      <dd>{d.imageTag || "n/a"}</dd>
                      <dt>Chart</dt>
                      <dd>{d.chartVersion || "n/a"}</dd>
                      <dt>Health</dt>
                      <dd>
                        <span className={healthBadgeClass(d.healthStatus)}>
                          {d.healthStatus || "Unknown"}
                        </span>
                      </dd>
                      <dt>Sync</dt>
                      <dd>{d.syncStatus || "Unknown"}</dd>
                      <dt>Deployed</dt>
                      <dd>{new Date(d.deployedAt).toLocaleString()}</dd>
                      <dt>By</dt>
                      <dd>{d.deployedBy}</dd>
                    </dl>
                  </>
                ) : (
                  <p className="text-muted">Not deployed.</p>
                )}
                {deployTier === tier && (
                  <form onSubmit={handleDeploy} style={{ marginTop: "12px" }}>
                    <div className="form-group">
                      <label>Image Tag</label>
                      <input
                        type="text"
                        placeholder="v1.2.3"
                        value={deployForm.imageTag}
                        onChange={(e) =>
                          setDeployForm({
                            ...deployForm,
                            imageTag: e.target.value,
                          })
                        }
                      />
                    </div>
                    <div className="form-group">
                      <label>Chart Version</label>
                      <input
                        type="text"
                        value={deployForm.chartVersion}
                        onChange={(e) =>
                          setDeployForm({
                            ...deployForm,
                            chartVersion: e.target.value,
                          })
                        }
                      />
                    </div>
                    <div className="form-group">
                      <label>Git SHA</label>
                      <input
                        type="text"
                        value={deployForm.gitSha}
                        onChange={(e) =>
                          setDeployForm({
                            ...deployForm,
                            gitSha: e.target.value,
                          })
                        }
                      />
                    </div>
                    <div className="form-group">
                      <label>Strategy Override</label>
                      <select
                        value={deployForm.strategy}
                        onChange={(e) =>
                          setDeployForm({
                            ...deployForm,
                            strategy: e.target.value as
                              | ""
                              | "rolling"
                              | "bluegreen"
                              | "canary",
                          })
                        }
                      >
                        <option value="">(default)</option>
                        <option value="rolling">rolling</option>
                        <option value="bluegreen">bluegreen</option>
                        <option value="canary">canary</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label>Value Overrides (JSON)</label>
                      <textarea
                        rows={3}
                        style={{
                          padding: "8px 12px",
                          border: "1px solid var(--border)",
                          borderRadius: "var(--radius-sm)",
                          fontFamily: "monospace",
                          fontSize: "12px",
                        }}
                        value={deployForm.valueOverrides}
                        onChange={(e) =>
                          setDeployForm({
                            ...deployForm,
                            valueOverrides: e.target.value,
                          })
                        }
                      />
                    </div>
                    <button
                      className="btn btn-primary btn-sm"
                      type="submit"
                      disabled={deploying}
                    >
                      {deploying ? "Deploying..." : "Deploy"}
                    </button>
                  </form>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="detail-section">
        <h3>History</h3>
        {!history || history.events.length === 0 ? (
          <p className="text-muted">No deployment history yet.</p>
        ) : (
          <table className="table table-compact">
            <thead>
              <tr>
                <th>When</th>
                <th>Event</th>
                <th>From</th>
                <th>To</th>
                <th>Actor</th>
              </tr>
            </thead>
            <tbody>
              {history.events.map((e) => (
                <tr key={e.id}>
                  <td>{new Date(e.occurredAt).toLocaleString()}</td>
                  <td>{e.eventType}</td>
                  <td className="text-mono">{e.fromVersion || "—"}</td>
                  <td className="text-mono">{e.toVersion || "—"}</td>
                  <td>{e.actor}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
