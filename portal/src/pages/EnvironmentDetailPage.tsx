import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  getEnvironment,
  updateEnvironment,
  deleteEnvironment,
} from "@/api/environments";
import type { Environment, EnvironmentUpdate } from "@/types";

export default function EnvironmentDetailPage() {
  const { slug, tier } = useParams<{ slug: string; tier: string }>();
  const navigate = useNavigate();
  const [env, setEnv] = useState<Environment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  const [cpuRequest, setCpuRequest] = useState("");
  const [cpuLimit, setCpuLimit] = useState("");
  const [memoryRequest, setMemoryRequest] = useState("");
  const [memoryLimit, setMemoryLimit] = useState("");
  const [pods, setPods] = useState("");
  const [services, setServices] = useState("");

  const fetchEnvironment = useCallback(async () => {
    if (!slug || !tier) return;
    try {
      setLoading(true);
      const data = await getEnvironment(slug, tier);
      setEnv(data);
      setCpuRequest(data.resourceQuota?.cpuRequest ?? "");
      setCpuLimit(data.resourceQuota?.cpuLimit ?? "");
      setMemoryRequest(data.resourceQuota?.memoryRequest ?? "");
      setMemoryLimit(data.resourceQuota?.memoryLimit ?? "");
      setPods(String(data.resourceQuota?.pods ?? ""));
      setServices(String(data.resourceQuota?.services ?? ""));
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load environment"
      );
    } finally {
      setLoading(false);
    }
  }, [slug, tier]);

  useEffect(() => {
    fetchEnvironment();
  }, [fetchEnvironment]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!slug || !tier) return;
    setSaving(true);
    const data: EnvironmentUpdate = {
      resourceQuota: {
        cpuRequest,
        cpuLimit,
        memoryRequest,
        memoryLimit,
        pods: parseInt(pods, 10),
        services: parseInt(services, 10),
      },
    };
    try {
      await updateEnvironment(slug, tier, data);
      setEditing(false);
      await fetchEnvironment();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to update environment"
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!slug || !tier) return;
    const confirmed = window.confirm(
      `Delete the ${tier} environment? This will remove the namespace and all resources.`
    );
    if (!confirmed) return;
    try {
      await deleteEnvironment(slug, tier);
      navigate(`/teams/${slug}/environments`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to delete environment"
      );
    }
  }

  if (loading) {
    return <div className="loading-screen"><p>Loading environment...</p></div>;
  }

  if (error && !env) {
    return (
      <div className="page">
        <div className="alert alert-error">{error}</div>
      </div>
    );
  }

  if (!env) return null;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>
            <span className={`badge badge-tier-${env.tier}`}>{env.tier}</span>{" "}
            Environment
          </h2>
          <p className="text-mono text-muted">{env.namespaceName}</p>
        </div>
        <div className="btn-group">
          <button
            className="btn"
            onClick={() => setEditing(!editing)}
          >
            {editing ? "Cancel" : "Edit"}
          </button>
          <button className="btn btn-danger" onClick={handleDelete}>
            Delete
          </button>
        </div>
      </div>

      <div className="env-nav-links">
        <Link to={`/teams/${slug}/environments/${tier}/security`}>
          Security Posture
        </Link>
        <Link to={`/teams/${slug}/environments/${tier}/metrics`}>
          Metrics
        </Link>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="detail-section">
        <h3>Status</h3>
        <dl className="detail-grid">
          <dt>Phase</dt>
          <dd>
            <span className={`badge badge-phase-${env.phase}`}>
              {env.phase}
            </span>
          </dd>
          <dt>Namespace</dt>
          <dd className="text-mono">{env.namespaceName}</dd>
          <dt>Created</dt>
          <dd>{new Date(env.createdAt).toLocaleDateString()}</dd>
          <dt>Updated</dt>
          <dd>{new Date(env.updatedAt).toLocaleDateString()}</dd>
        </dl>
      </div>

      <div className="detail-section">
        <h3>Resource Quota</h3>
        {editing ? (
          <form className="form-card" onSubmit={handleSave}>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="edit-cpuReq">CPU Requests</label>
                <input
                  id="edit-cpuReq"
                  type="text"
                  value={cpuRequest}
                  onChange={(e) => setCpuRequest(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label htmlFor="edit-cpuLim">CPU Limits</label>
                <input
                  id="edit-cpuLim"
                  type="text"
                  value={cpuLimit}
                  onChange={(e) => setCpuLimit(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label htmlFor="edit-memReq">Memory Requests</label>
                <input
                  id="edit-memReq"
                  type="text"
                  value={memoryRequest}
                  onChange={(e) => setMemoryRequest(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label htmlFor="edit-memLim">Memory Limits</label>
                <input
                  id="edit-memLim"
                  type="text"
                  value={memoryLimit}
                  onChange={(e) => setMemoryLimit(e.target.value)}
                />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="edit-pods">Pods</label>
                <input
                  id="edit-pods"
                  type="number"
                  value={pods}
                  onChange={(e) => setPods(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label htmlFor="edit-services">Services</label>
                <input
                  id="edit-services"
                  type="number"
                  value={services}
                  onChange={(e) => setServices(e.target.value)}
                />
              </div>
            </div>
            <button
              className="btn btn-primary"
              type="submit"
              disabled={saving}
            >
              {saving ? "Saving..." : "Save Changes"}
            </button>
          </form>
        ) : (
          <table className="table table-compact">
            <thead>
              <tr>
                <th>Resource</th>
                <th>Value</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>CPU Requests</td>
                <td className="text-mono">{env.resourceQuota?.cpuRequest}</td>
              </tr>
              <tr>
                <td>CPU Limits</td>
                <td className="text-mono">{env.resourceQuota?.cpuLimit}</td>
              </tr>
              <tr>
                <td>Memory Requests</td>
                <td className="text-mono">
                  {env.resourceQuota?.memoryRequest}
                </td>
              </tr>
              <tr>
                <td>Memory Limits</td>
                <td className="text-mono">
                  {env.resourceQuota?.memoryLimit}
                </td>
              </tr>
              <tr>
                <td>Pods</td>
                <td className="text-mono">{env.resourceQuota?.pods}</td>
              </tr>
              <tr>
                <td>Services</td>
                <td className="text-mono">{env.resourceQuota?.services}</td>
              </tr>
              <tr>
                <td>PVCs</td>
                <td className="text-mono">
                  {env.resourceQuota?.persistentVolumeClaims}
                </td>
              </tr>
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
