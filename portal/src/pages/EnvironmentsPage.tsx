import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { listEnvironments, createEnvironment } from "@/api/environments";
import type { Environment, EnvironmentCreate } from "@/types";

type Tier = "dev" | "staging" | "prod";
const TIERS: Tier[] = ["dev", "staging", "prod"];

export default function EnvironmentsPage() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [selectedTier, setSelectedTier] = useState<Tier>("dev");
  const [cpuRequests, setCpuRequests] = useState("2");
  const [cpuLimits, setCpuLimits] = useState("4");
  const [memoryRequests, setMemoryRequests] = useState("2Gi");
  const [memoryLimits, setMemoryLimits] = useState("4Gi");
  const [submitting, setSubmitting] = useState(false);

  const fetchEnvironments = useCallback(async () => {
    if (!slug) return;
    try {
      setLoading(true);
      const data = await listEnvironments(slug);
      setEnvironments(data);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load environments"
      );
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    fetchEnvironments();
  }, [fetchEnvironments]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!slug) return;
    setSubmitting(true);

    const data: EnvironmentCreate = {
      tier: selectedTier,
      resourceQuota: {
        cpuRequests,
        cpuLimits,
        memoryRequests,
        memoryLimits,
      },
    };

    try {
      await createEnvironment(slug, data);
      setShowForm(false);
      await fetchEnvironments();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create environment"
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <div className="loading-screen"><p>Loading environments...</p></div>;
  }

  return (
    <div>
      <div className="section-header">
        <h3>Environments</h3>
        <button
          className="btn btn-primary"
          onClick={() => setShowForm(!showForm)}
        >
          {showForm ? "Cancel" : "Create Environment"}
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {showForm && (
        <form className="card form-card" onSubmit={handleCreate}>
          <h4>New Environment</h4>
          <div className="form-group">
            <label htmlFor="tier">Tier</label>
            <select
              id="tier"
              value={selectedTier}
              onChange={(e) => setSelectedTier(e.target.value as Tier)}
            >
              {TIERS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <fieldset className="form-fieldset">
            <legend>Resource Quota</legend>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="cpuReq">CPU Requests</label>
                <input
                  id="cpuReq"
                  type="text"
                  value={cpuRequests}
                  onChange={(e) => setCpuRequests(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label htmlFor="cpuLim">CPU Limits</label>
                <input
                  id="cpuLim"
                  type="text"
                  value={cpuLimits}
                  onChange={(e) => setCpuLimits(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label htmlFor="memReq">Memory Requests</label>
                <input
                  id="memReq"
                  type="text"
                  value={memoryRequests}
                  onChange={(e) => setMemoryRequests(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label htmlFor="memLim">Memory Limits</label>
                <input
                  id="memLim"
                  type="text"
                  value={memoryLimits}
                  onChange={(e) => setMemoryLimits(e.target.value)}
                />
              </div>
            </div>
          </fieldset>
          <button
            className="btn btn-primary"
            type="submit"
            disabled={submitting}
          >
            {submitting ? "Creating..." : "Create Environment"}
          </button>
        </form>
      )}

      {environments.length === 0 && !showForm ? (
        <div className="empty-state">
          <p>No environments provisioned. Create one to get started.</p>
        </div>
      ) : (
        <div className="card-grid">
          {environments.map((env) => (
            <div
              key={env.id}
              className="card card-clickable"
              onClick={() =>
                navigate(`/teams/${slug}/environments/${env.tier}`)
              }
            >
              <div className="card-header-row">
                <span className={`badge badge-tier-${env.tier}`}>
                  {env.tier}
                </span>
                <span className={`badge badge-phase-${env.phase}`}>
                  {env.phase}
                </span>
              </div>
              <p className="text-mono">{env.namespaceName}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
