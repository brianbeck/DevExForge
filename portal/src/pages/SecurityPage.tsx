import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  getViolations,
  getVulnerabilities,
  getSecurityEvents,
  getComplianceSummary,
} from "@/api/security";
import type {
  Violation,
  VulnerabilityReport,
  SecurityEvent,
  ComplianceSummary,
} from "@/api/security";

type Tab = "violations" | "vulnerabilities" | "events";

export default function SecurityPage() {
  const { slug, tier } = useParams<{ slug: string; tier: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("violations");

  const [compliance, setCompliance] = useState<ComplianceSummary | null>(null);
  const [violations, setViolations] = useState<Violation[]>([]);
  const [vulnerabilities, setVulnerabilities] = useState<VulnerabilityReport[]>([]);
  const [events, setEvents] = useState<SecurityEvent[]>([]);

  useEffect(() => {
    if (!slug || !tier) return;

    async function fetchAll() {
      try {
        setLoading(true);
        const [compData, violData, vulnData, evtData] = await Promise.all([
          getComplianceSummary(slug!, tier!),
          getViolations(slug!, tier!),
          getVulnerabilities(slug!, tier!),
          getSecurityEvents(slug!, tier!),
        ]);
        setCompliance(compData);
        setViolations(violData.violations);
        setVulnerabilities(vulnData.vulnerabilities);
        setEvents(evtData.events);
        setError(null);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load security data"
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
        <p>Loading security data...</p>
      </div>
    );
  }

  if (error && !compliance) {
    return (
      <div className="page">
        <div className="alert alert-error">{error}</div>
      </div>
    );
  }

  function scoreClass(score: number) {
    if (score >= 80) return "compliant";
    if (score >= 50) return "warning";
    return "critical";
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Security Posture</h2>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {compliance && (
        <div className={`compliance-card ${scoreClass(compliance.score)}`}>
          <div className={`score-circle ${scoreClass(compliance.score)}`}>
            {compliance.score}
          </div>
          <div>
            <h3 style={{ marginBottom: "0.5rem" }}>
              Compliance: {compliance.status}
            </h3>
            <div className="compliance-stats">
              <div className="compliance-stat">
                <div className="value">{compliance.policyViolations}</div>
                <div className="label">Policy Violations</div>
              </div>
              <div className="compliance-stat">
                <div className="value">{compliance.criticalCVEs}</div>
                <div className="label">Critical CVEs</div>
              </div>
              <div className="compliance-stat">
                <div className="value">{compliance.highCVEs}</div>
                <div className="label">High CVEs</div>
              </div>
              <div className="compliance-stat">
                <div className="value">{compliance.securityEvents}</div>
                <div className="label">Security Events</div>
              </div>
              <div className="compliance-stat">
                <div className="value">{compliance.imageCount}</div>
                <div className="label">Images Scanned</div>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="tab-nav">
        <button
          className={`tab ${activeTab === "violations" ? "active" : ""}`}
          onClick={() => setActiveTab("violations")}
        >
          Violations ({violations.length})
        </button>
        <button
          className={`tab ${activeTab === "vulnerabilities" ? "active" : ""}`}
          onClick={() => setActiveTab("vulnerabilities")}
        >
          Vulnerabilities ({vulnerabilities.length})
        </button>
        <button
          className={`tab ${activeTab === "events" ? "active" : ""}`}
          onClick={() => setActiveTab("events")}
        >
          Falco Events ({events.length})
        </button>
      </div>

      {activeTab === "violations" && (
        <>
          {violations.length === 0 ? (
            <div className="empty-state">No policy violations found.</div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Constraint Kind</th>
                  <th>Constraint Name</th>
                  <th>Message</th>
                  <th>Resource</th>
                </tr>
              </thead>
              <tbody>
                {violations.map((v, i) => (
                  <tr key={i}>
                    <td className="text-mono">{v.constraintKind}</td>
                    <td className="text-mono">{v.constraintName}</td>
                    <td>{v.message}</td>
                    <td className="text-mono">
                      {v.resource.kind}/{v.resource.name}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}

      {activeTab === "vulnerabilities" && (
        <>
          {vulnerabilities.length === 0 ? (
            <div className="empty-state">No vulnerability reports found.</div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Image</th>
                  <th>Critical</th>
                  <th>High</th>
                  <th>Medium</th>
                  <th>Low</th>
                  <th>Scanner</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {vulnerabilities.map((v, i) => (
                  <tr key={i}>
                    <td className="text-mono">{v.image}</td>
                    <td>
                      <span className={v.critical > 0 ? "severity-critical" : ""}>
                        {v.critical}
                      </span>
                    </td>
                    <td>
                      <span className={v.high > 0 ? "severity-high" : ""}>
                        {v.high}
                      </span>
                    </td>
                    <td>{v.medium}</td>
                    <td>{v.low}</td>
                    <td>{v.scanner}</td>
                    <td>{new Date(v.updatedAt).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}

      {activeTab === "events" && (
        <>
          {events.length === 0 ? (
            <div className="empty-state">No security events found.</div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Severity</th>
                  <th>Message</th>
                  <th>Object</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e, i) => (
                  <tr key={i}>
                    <td>{new Date(e.timestamp).toLocaleString()}</td>
                    <td>
                      <span
                        className={`severity-${e.severity.toLowerCase()}`}
                      >
                        {e.severity}
                      </span>
                    </td>
                    <td>{e.message}</td>
                    <td className="text-mono">
                      {e.involvedObject.kind}/{e.involvedObject.name}
                    </td>
                    <td>{e.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  );
}
