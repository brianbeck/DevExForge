import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  getResourceUsage,
  getMetrics,
  getDashboards,
} from "@/api/observability";
import type { ResourceQuotaUsage, Dashboard } from "@/api/observability";

function parseUsagePercent(used: string, hard: string): number {
  const usedNum = parseFloat(used) || 0;
  const hardNum = parseFloat(hard) || 1;
  return Math.min(Math.round((usedNum / hardNum) * 100), 100);
}

function usageBarClass(pct: number): string {
  if (pct >= 80) return "high";
  if (pct >= 50) return "medium";
  return "low";
}

export default function MetricsPage() {
  const { slug, tier } = useParams<{ slug: string; tier: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [quotas, setQuotas] = useState<ResourceQuotaUsage[]>([]);
  const [metrics, setMetrics] = useState<Record<string, string | null>>({});
  const [dashboards, setDashboards] = useState<Dashboard[]>([]);

  useEffect(() => {
    if (!slug || !tier) return;

    async function fetchAll() {
      try {
        setLoading(true);
        const [usageData, metricsData, dashData] = await Promise.all([
          getResourceUsage(slug!, tier!),
          getMetrics(slug!, tier!),
          getDashboards(slug!, tier!),
        ]);
        setQuotas(usageData.quotas);
        setMetrics(metricsData.metrics);
        setDashboards(dashData.dashboards);
        setError(null);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load metrics"
        );
      } finally {
        setLoading(false);
      }
    }

    fetchAll();
  }, [slug, tier]);

  if (loading) {
    return (
      <div className="loading-screen">
        <p>Loading metrics...</p>
      </div>
    );
  }

  if (error && quotas.length === 0) {
    return (
      <div className="page">
        <div className="alert alert-error">{error}</div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Metrics &amp; Observability</h2>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="detail-section">
        <h3>Current Metrics</h3>
        <div className="metric-cards">
          <div className="metric-card">
            <div className="value">{metrics.cpu_usage ?? "N/A"}</div>
            <div className="label">CPU Usage</div>
          </div>
          <div className="metric-card">
            <div className="value">{metrics.memory_usage ?? "N/A"}</div>
            <div className="label">Memory Usage</div>
          </div>
          <div className="metric-card">
            <div className="value">{metrics.pod_count ?? "N/A"}</div>
            <div className="label">Pod Count</div>
          </div>
        </div>
      </div>

      <div className="detail-section">
        <h3>Resource Usage</h3>
        {quotas.length === 0 ? (
          <div className="empty-state">No resource quotas found.</div>
        ) : (
          quotas.map((quota) => (
            <div key={quota.name} style={{ marginBottom: "1.5rem" }}>
              <h4 style={{ fontSize: "14px", marginBottom: "0.5rem" }}>
                {quota.name}
              </h4>
              <table className="table table-compact">
                <thead>
                  <tr>
                    <th>Resource</th>
                    <th>Used</th>
                    <th>Hard Limit</th>
                    <th>Usage</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.keys(quota.hard).map((resource) => {
                    const used = quota.used[resource] ?? "0";
                    const hard = quota.hard[resource];
                    const pct = parseUsagePercent(used, hard);
                    return (
                      <tr key={resource}>
                        <td className="text-mono">{resource}</td>
                        <td className="text-mono">{used}</td>
                        <td className="text-mono">{hard}</td>
                        <td style={{ minWidth: "150px" }}>
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "8px",
                            }}
                          >
                            <div className="usage-bar-container">
                              <div
                                className={`usage-bar ${usageBarClass(pct)}`}
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                            <span
                              style={{ fontSize: "12px", whiteSpace: "nowrap" }}
                            >
                              {pct}%
                            </span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ))
        )}
      </div>

      <div className="detail-section">
        <h3>Grafana Dashboards</h3>
        {dashboards.length === 0 ? (
          <div className="empty-state">No dashboards available.</div>
        ) : (
          <div className="dashboard-list">
            {dashboards.map((d) => (
              <a
                key={d.name}
                href={d.url}
                target="_blank"
                rel="noopener noreferrer"
                className="dashboard-link"
              >
                {d.name}
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
