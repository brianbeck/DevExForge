import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getAuditLog, getTeamAuditLog } from "@/api/audit";
import type { AuditEntry, AuditLogList } from "@/api/audit";

const PAGE_SIZE = 25;

export default function AuditLogPage() {
  const { slug } = useParams<{ slug?: string }>();
  const [data, setData] = useState<AuditLogList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const [filters, setFilters] = useState({
    teamSlug: slug || "",
    userEmail: "",
    action: "",
  });

  async function fetchAudit(currentOffset: number) {
    try {
      setLoading(true);
      let result: AuditLogList;
      if (slug) {
        result = await getTeamAuditLog(slug, {
          limit: PAGE_SIZE,
          offset: currentOffset,
        });
      } else {
        result = await getAuditLog({
          teamSlug: filters.teamSlug || undefined,
          userEmail: filters.userEmail || undefined,
          action: filters.action || undefined,
          limit: PAGE_SIZE,
          offset: currentOffset,
        });
      }
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load audit log");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setOffset(0);
    fetchAudit(0);
  }, [slug]);

  function handleFilter() {
    setOffset(0);
    fetchAudit(0);
  }

  function handlePrev() {
    const newOffset = Math.max(0, offset - PAGE_SIZE);
    setOffset(newOffset);
    fetchAudit(newOffset);
  }

  function handleNext() {
    if (!data) return;
    const newOffset = offset + PAGE_SIZE;
    if (newOffset < data.total) {
      setOffset(newOffset);
      fetchAudit(newOffset);
    }
  }

  function toggleExpand(id: number) {
    setExpandedId(expandedId === id ? null : id);
  }

  function renderRow(entry: AuditEntry) {
    const isExpanded = expandedId === entry.id;
    return (
      <>
        <tr
          key={entry.id}
          className="audit-expandable"
          onClick={() => toggleExpand(entry.id)}
        >
          <td>{new Date(entry.timestamp).toLocaleString()}</td>
          <td>{entry.userEmail}</td>
          <td>{entry.action}</td>
          <td>{entry.resourceType}</td>
          <td className="text-mono">{entry.resourceId || "-"}</td>
          <td>{entry.teamSlug || "-"}</td>
          <td>{entry.responseStatus ?? "-"}</td>
        </tr>
        {isExpanded && entry.requestBody && (
          <tr key={`${entry.id}-detail`}>
            <td colSpan={7} className="audit-detail">
              <pre>{JSON.stringify(entry.requestBody, null, 2)}</pre>
            </td>
          </tr>
        )}
      </>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>{slug ? `Audit Log: ${slug}` : "Audit Log"}</h2>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {!slug && (
        <div className="audit-filters">
          <input
            type="text"
            placeholder="Team slug"
            value={filters.teamSlug}
            onChange={(e) =>
              setFilters({ ...filters, teamSlug: e.target.value })
            }
          />
          <input
            type="text"
            placeholder="User email"
            value={filters.userEmail}
            onChange={(e) =>
              setFilters({ ...filters, userEmail: e.target.value })
            }
          />
          <select
            value={filters.action}
            onChange={(e) =>
              setFilters({ ...filters, action: e.target.value })
            }
          >
            <option value="">All actions</option>
            <option value="create">create</option>
            <option value="update">update</option>
            <option value="delete">delete</option>
            <option value="promote">promote</option>
          </select>
          <button className="btn btn-primary btn-sm" onClick={handleFilter}>
            Filter
          </button>
        </div>
      )}

      {loading ? (
        <div className="loading-screen">
          <p>Loading audit log...</p>
        </div>
      ) : (
        <>
          <table className="table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>User</th>
                <th>Action</th>
                <th>Resource</th>
                <th>Resource ID</th>
                <th>Team</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data && data.entries.length > 0 ? (
                data.entries.map((entry) => renderRow(entry))
              ) : (
                <tr>
                  <td colSpan={7} className="text-muted" style={{ textAlign: "center" }}>
                    No audit entries found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          {data && data.total > PAGE_SIZE && (
            <div className="pagination">
              <button
                className="btn btn-sm"
                onClick={handlePrev}
                disabled={offset === 0}
              >
                Previous
              </button>
              <span className="text-muted">
                {offset + 1}&ndash;{Math.min(offset + PAGE_SIZE, data.total)} of{" "}
                {data.total}
              </span>
              <button
                className="btn btn-sm"
                onClick={handleNext}
                disabled={offset + PAGE_SIZE >= data.total}
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
