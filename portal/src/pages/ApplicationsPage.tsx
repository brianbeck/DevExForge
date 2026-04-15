import { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  listApplications,
  getTeamInventory,
  createApplication,
} from "@/api/applications";
import type {
  Application,
  ApplicationCreate,
  InventoryResponse,
} from "@/api/applications";

const TIERS = ["dev", "staging", "production"] as const;

function formatAge(iso: string | null): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diff = Math.max(0, now - then);
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}

export function healthBadgeClass(status: string | null | undefined): string {
  const s = (status || "").toLowerCase();
  if (s === "healthy") return "health-badge healthy";
  if (s === "progressing") return "health-badge progressing";
  if (s === "degraded") return "health-badge degraded";
  if (s === "missing") return "health-badge missing";
  if (s === "suspended") return "health-badge suspended";
  return "health-badge unknown";
}

export default function ApplicationsPage() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const [apps, setApps] = useState<Application[]>([]);
  const [inventory, setInventory] = useState<InventoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formData, setFormData] = useState<ApplicationCreate>({
    name: "",
    displayName: "",
    description: "",
    repoUrl: "",
    chartPath: "",
    ownerEmail: "",
    defaultStrategy: "rolling",
  });

  const fetchData = useCallback(async () => {
    if (!slug) return;
    try {
      setLoading(true);
      const [appsData, invData] = await Promise.all([
        listApplications(slug),
        getTeamInventory(slug),
      ]);
      setApps(appsData);
      setInventory(invData);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load applications"
      );
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!slug) return;
    setSubmitting(true);
    try {
      const payload: ApplicationCreate = {
        name: formData.name,
        displayName: formData.displayName,
        ownerEmail: formData.ownerEmail,
        defaultStrategy: formData.defaultStrategy,
      };
      if (formData.description) payload.description = formData.description;
      if (formData.repoUrl) payload.repoUrl = formData.repoUrl;
      if (formData.chartPath) payload.chartPath = formData.chartPath;
      if (formData.chartRepoUrl) payload.chartRepoUrl = formData.chartRepoUrl;
      if (formData.imageRepo) payload.imageRepo = formData.imageRepo;
      await createApplication(slug, payload);
      setShowForm(false);
      setFormData({
        name: "",
        displayName: "",
        description: "",
        repoUrl: "",
        chartPath: "",
        ownerEmail: "",
        defaultStrategy: "rolling",
      });
      await fetchData();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to register application"
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="loading-screen">
        <p>Loading applications...</p>
      </div>
    );
  }

  return (
    <div>
      <div className="section-header">
        <h3>Applications</h3>
        <button
          className="btn btn-primary"
          onClick={() => setShowForm(!showForm)}
        >
          {showForm ? "Cancel" : "Register Application"}
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {showForm && (
        <form className="card form-card" onSubmit={handleCreate}>
          <h4>Register Application</h4>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="app-name">Name</label>
              <input
                id="app-name"
                type="text"
                required
                placeholder="my-app"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="app-displayName">Display Name</label>
              <input
                id="app-displayName"
                type="text"
                required
                placeholder="My Application"
                value={formData.displayName}
                onChange={(e) =>
                  setFormData({ ...formData, displayName: e.target.value })
                }
              />
            </div>
          </div>
          <div className="form-group">
            <label htmlFor="app-description">Description</label>
            <input
              id="app-description"
              type="text"
              value={formData.description || ""}
              onChange={(e) =>
                setFormData({ ...formData, description: e.target.value })
              }
            />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="app-repoUrl">Repo URL</label>
              <input
                id="app-repoUrl"
                type="text"
                placeholder="https://github.com/..."
                value={formData.repoUrl || ""}
                onChange={(e) =>
                  setFormData({ ...formData, repoUrl: e.target.value })
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="app-chartPath">Chart Path</label>
              <input
                id="app-chartPath"
                type="text"
                placeholder="charts/my-app"
                value={formData.chartPath || ""}
                onChange={(e) =>
                  setFormData({ ...formData, chartPath: e.target.value })
                }
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="app-imageRepo">Image Repository</label>
              <input
                id="app-imageRepo"
                type="text"
                placeholder="ghcr.io/org/app"
                value={formData.imageRepo || ""}
                onChange={(e) =>
                  setFormData({ ...formData, imageRepo: e.target.value })
                }
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="app-owner">Owner Email</label>
              <input
                id="app-owner"
                type="email"
                required
                value={formData.ownerEmail}
                onChange={(e) =>
                  setFormData({ ...formData, ownerEmail: e.target.value })
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="app-strategy">Default Strategy</label>
              <select
                id="app-strategy"
                value={formData.defaultStrategy}
                onChange={(e) =>
                  setFormData({
                    ...formData,
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
          <button
            className="btn btn-primary"
            type="submit"
            disabled={submitting}
          >
            {submitting ? "Registering..." : "Register"}
          </button>
        </form>
      )}

      {apps.length === 0 && !showForm ? (
        <div className="empty-state">
          <p>
            No applications registered yet. Register one to start deploying.
          </p>
        </div>
      ) : (
        <InventoryGrid
          rows={inventory?.rows || []}
          onRowClick={(name) =>
            navigate(`/teams/${slug}/applications/${name}`)
          }
        />
      )}
    </div>
  );
}

export function InventoryGrid({
  rows,
  onRowClick,
  showTeam = false,
  onTeamRowClick,
}: {
  rows: InventoryResponse["rows"];
  onRowClick?: (name: string) => void;
  showTeam?: boolean;
  onTeamRowClick?: (teamSlug: string, name: string) => void;
}) {
  return (
    <div className={`inventory-grid${showTeam ? " with-team" : ""}`}>
      <div className="inventory-header">
        {showTeam && <div className="inventory-cell">Team</div>}
        <div className="inventory-cell">Application</div>
        {TIERS.map((t) => (
          <div key={t} className="inventory-cell">
            {t}
          </div>
        ))}
      </div>
      {rows.map((row) => (
        <div
          key={`${row.teamSlug}-${row.id}`}
          className="inventory-row"
          onClick={() => {
            if (showTeam && onTeamRowClick) {
              onTeamRowClick(row.teamSlug, row.name);
            } else if (onRowClick) {
              onRowClick(row.name);
            }
          }}
        >
          {showTeam && (
            <div className="inventory-cell">
              <div className="inventory-version">{row.teamSlug}</div>
            </div>
          )}
          <div className="inventory-cell">
            <div className="inventory-version">{row.displayName}</div>
            <div className="inventory-meta">{row.ownerEmail}</div>
          </div>
          {TIERS.map((t) => {
            const cell = row.deployments[t];
            if (!cell || !cell.imageTag) {
              return (
                <div key={t} className="inventory-cell empty">
                  not deployed
                </div>
              );
            }
            return (
              <div key={t} className="inventory-cell">
                <div className="inventory-version">{cell.imageTag}</div>
                <div className="inventory-meta">
                  <span className={healthBadgeClass(cell.healthStatus)}>
                    {cell.healthStatus || "Unknown"}
                  </span>{" "}
                  {formatAge(cell.deployedAt)}
                </div>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
