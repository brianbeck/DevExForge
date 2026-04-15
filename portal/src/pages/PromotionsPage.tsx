import { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  listAllPromotions,
  listTeamPromotions,
  approvePromotion,
  rejectPromotion,
  cancelPromotion,
} from "@/api/promotions";
import type { PromotionRequest, PromotionStatus } from "@/api/promotions";

export function promotionStatusClass(status: PromotionStatus): string {
  return `promo-badge promo-badge-${status}`;
}

const STATUSES: PromotionStatus[] = [
  "pending_gates",
  "pending_approval",
  "approved",
  "executing",
  "completed",
  "rejected",
  "failed",
  "rolled_back",
  "cancelled",
];

const TIERS = ["dev", "staging", "production"];

export default function PromotionsPage() {
  const { slug, name } = useParams<{ slug?: string; name?: string }>();
  const navigate = useNavigate();
  const teamScoped = Boolean(slug && name);
  const [promos, setPromos] = useState<PromotionRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [tierFilter, setTierFilter] = useState<string>("");
  const [openMenu, setOpenMenu] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      let data: PromotionRequest[];
      if (teamScoped && slug && name) {
        data = await listTeamPromotions(slug, name);
      } else {
        data = await listAllPromotions(
          statusFilter || undefined,
          tierFilter || undefined
        );
      }
      setPromos(data);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load promotions"
      );
    } finally {
      setLoading(false);
    }
  }, [teamScoped, slug, name, statusFilter, tierFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function handleApprove(id: string) {
    try {
      await approvePromotion(id);
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approve failed");
    }
  }

  async function handleReject(id: string) {
    const reason = prompt("Rejection reason:");
    if (!reason) return;
    try {
      await rejectPromotion(id, reason);
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reject failed");
    }
  }

  async function handleCancel(id: string) {
    if (!confirm("Cancel this promotion request?")) return;
    try {
      await cancelPromotion(id);
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cancel failed");
    }
  }

  if (loading) {
    return (
      <div className="loading-screen">
        <p>Loading promotions...</p>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>
          {teamScoped
            ? `Promotions — ${name}`
            : "Promotions"}
        </h2>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {!teamScoped && (
        <div className="audit-filters">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <select
            value={tierFilter}
            onChange={(e) => setTierFilter(e.target.value)}
          >
            <option value="">All tiers</option>
            {TIERS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
      )}

      {promos.length === 0 ? (
        <div className="empty-state">
          <p>No promotion requests found.</p>
        </div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>App</th>
              <th>From → To</th>
              <th>Strategy</th>
              <th>Status</th>
              <th>Requested By</th>
              <th>Requested At</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {promos.map((p) => (
              <tr key={p.id}>
                <td>
                  <span className="text-mono">
                    {p.teamSlug ?? "—"}/{p.applicationName ?? "—"}
                  </span>
                </td>
                <td>
                  {p.fromTier || "—"} → {p.targetTier}
                  <div className="inventory-meta">
                    → {p.imageTag ?? "—"}
                  </div>
                </td>
                <td>{p.strategy ?? "rolling"}</td>
                <td>
                  <span className={promotionStatusClass(p.status)}>
                    {p.status}
                  </span>
                </td>
                <td>{p.requestedBy}</td>
                <td>{new Date(p.requestedAt).toLocaleString()}</td>
                <td>
                  <div className="promo-actions">
                    <button
                      className="btn btn-sm"
                      onClick={() =>
                        setOpenMenu(openMenu === p.id ? null : p.id)
                      }
                    >
                      Actions ▾
                    </button>
                    {openMenu === p.id && (
                      <div className="promo-menu">
                        <button
                          className="promo-menu-item"
                          onClick={() => {
                            setOpenMenu(null);
                            navigate(`/promotion-requests/${p.id}`);
                          }}
                        >
                          View Detail
                        </button>
                        {p.status === "pending_approval" && (
                          <button
                            className="promo-menu-item"
                            onClick={() => {
                              setOpenMenu(null);
                              handleApprove(p.id);
                            }}
                          >
                            Approve
                          </button>
                        )}
                        {(p.status === "pending_approval" ||
                          p.status === "pending_gates") && (
                          <button
                            className="promo-menu-item"
                            onClick={() => {
                              setOpenMenu(null);
                              handleReject(p.id);
                            }}
                          >
                            Reject
                          </button>
                        )}
                        {p.status.startsWith("pending") && (
                          <button
                            className="promo-menu-item"
                            onClick={() => {
                              setOpenMenu(null);
                              handleCancel(p.id);
                            }}
                          >
                            Cancel
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
