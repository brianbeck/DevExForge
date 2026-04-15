import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  getRolloutStatus,
  promoteRollout,
  pauseRollout,
  abortRollout,
} from "@/api/promotions";
import type { RolloutStatus } from "@/api/promotions";
import { ApiError } from "@/api/client";

export default function RolloutStatusPage() {
  const { slug, name } = useParams<{ slug: string; name: string }>();
  const [status, setStatus] = useState<RolloutStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notInstalled, setNotInstalled] = useState(false);

  const fetchData = useCallback(async () => {
    if (!slug || !name) return;
    try {
      setLoading(true);
      setNotInstalled(false);
      const data = await getRolloutStatus(slug, name, "production");
      setStatus(data);
      setError(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setNotInstalled(true);
        setStatus(null);
      } else {
        setError(
          err instanceof Error ? err.message : "Failed to load rollout"
        );
      }
    } finally {
      setLoading(false);
    }
  }, [slug, name]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function handleAction(action: "promote" | "pause" | "abort") {
    if (!slug || !name) return;
    try {
      if (action === "promote")
        await promoteRollout(slug, name, "production");
      else if (action === "pause")
        await pauseRollout(slug, name, "production");
      else if (action === "abort")
        await abortRollout(slug, name, "production");
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    }
  }

  if (loading) {
    return (
      <div className="loading-screen">
        <p>Loading rollout status...</p>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Rollout — {name}</h2>
        <button className="btn" onClick={fetchData}>
          Refresh
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {notInstalled && (
        <div className="card">
          <h3>Argo Rollouts not installed</h3>
          <p className="text-muted">
            Argo Rollouts is not installed on this cluster. Install it to
            enable canary and blue-green deployments.
          </p>
        </div>
      )}

      {status && (
        <>
          <div className="detail-section">
            <h3>Status</h3>
            <dl className="detail-grid">
              <dt>Strategy</dt>
              <dd>{status.strategy}</dd>
              <dt>Phase</dt>
              <dd>
                <span className={`rollout-phase rollout-phase-${status.phase}`}>
                  {status.phase}
                </span>
              </dd>
              {status.currentStepIndex !== null &&
                status.totalSteps !== null && (
                  <>
                    <dt>Step</dt>
                    <dd>
                      {status.currentStepIndex} / {status.totalSteps}
                    </dd>
                  </>
                )}
              {status.stableRevision && (
                <>
                  <dt>Stable</dt>
                  <dd className="text-mono">{status.stableRevision}</dd>
                </>
              )}
              {status.canaryRevision && (
                <>
                  <dt>Canary</dt>
                  <dd className="text-mono">{status.canaryRevision}</dd>
                </>
              )}
              {status.activeService && (
                <>
                  <dt>Active Service</dt>
                  <dd className="text-mono">{status.activeService}</dd>
                </>
              )}
              {status.previewService && (
                <>
                  <dt>Preview Service</dt>
                  <dd className="text-mono">{status.previewService}</dd>
                </>
              )}
              {status.message && (
                <>
                  <dt>Message</dt>
                  <dd>{status.message}</dd>
                </>
              )}
            </dl>
          </div>

          <div className="detail-section">
            <h3>Controls</h3>
            <div className="btn-group">
              <button
                className="btn btn-primary"
                onClick={() => handleAction("promote")}
              >
                Promote
              </button>
              <button className="btn" onClick={() => handleAction("pause")}>
                Pause
              </button>
              <button
                className="btn btn-danger"
                onClick={() => handleAction("abort")}
              >
                Abort
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
