import { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useKeycloak } from "@react-keycloak/web";
import {
  getPromotion,
  approvePromotion,
  rejectPromotion,
  forcePromotion,
  rollbackPromotion,
  cancelPromotion,
} from "@/api/promotions";
import type { PromotionRequestDetail } from "@/api/promotions";
import { promotionStatusClass } from "./PromotionsPage";

function isPlatformAdmin(
  tokenParsed: Record<string, unknown> | undefined
): boolean {
  if (!tokenParsed) return false;
  const realmAccess = tokenParsed.realm_access as
    | { roles?: string[] }
    | undefined;
  const roles = realmAccess?.roles || [];
  return (
    roles.includes("platform-admin") ||
    roles.includes("admin") ||
    roles.includes("devexforge-admin")
  );
}

type ModalKind = "reject" | "force" | "rollback" | null;

export default function PromotionRequestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { keycloak } = useKeycloak();
  const admin = isPlatformAdmin(
    keycloak.tokenParsed as Record<string, unknown> | undefined
  );

  const [promo, setPromo] = useState<PromotionRequestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [approveNotes, setApproveNotes] = useState("");
  const [modal, setModal] = useState<ModalKind>(null);
  const [modalReason, setModalReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fetchData = useCallback(async () => {
    if (!id) return;
    try {
      setLoading(true);
      const data = await getPromotion(id);
      setPromo(data);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load promotion"
      );
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function handleApprove() {
    if (!id) return;
    setSubmitting(true);
    try {
      await approvePromotion(id, approveNotes || undefined);
      setApproveNotes("");
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approve failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCancel() {
    if (!id) return;
    if (!confirm("Cancel this promotion request?")) return;
    try {
      await cancelPromotion(id);
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cancel failed");
    }
  }

  async function handleModalSubmit() {
    if (!id || !modal || !modalReason.trim()) return;
    setSubmitting(true);
    try {
      if (modal === "reject") await rejectPromotion(id, modalReason);
      else if (modal === "force") await forcePromotion(id, modalReason);
      else if (modal === "rollback")
        await rollbackPromotion(id, modalReason);
      setModal(null);
      setModalReason("");
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="loading-screen">
        <p>Loading promotion request...</p>
      </div>
    );
  }

  if (error || !promo) {
    return (
      <div className="page">
        <div className="alert alert-error">
          {error || "Promotion request not found"}
        </div>
      </div>
    );
  }

  const s = promo.status;
  const canApprove = s === "pending_approval";
  const canReject = s === "pending_approval" || s === "pending_gates";
  const canForce =
    admin &&
    (s === "pending_gates" || s === "pending_approval" || s === "rejected");
  const canRollback =
    s === "executing" || s === "completed" || s === "failed";
  const canCancel = s.startsWith("pending");

  return (
    <div className="page">
      <div className="page-header">
        <h2>Promotion Request</h2>
        <button
          className="btn"
          onClick={() =>
            navigate(
              `/teams/${promo.teamSlug}/applications/${promo.applicationName}`
            )
          }
        >
          View Application
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="detail-section">
        <h3>Request</h3>
        <dl className="detail-grid">
          <dt>Application</dt>
          <dd className="text-mono">
            {promo.teamSlug}/{promo.applicationName}
          </dd>
          <dt>From → To</dt>
          <dd>
            {promo.fromTier || "—"} → {promo.toTier}
          </dd>
          <dt>Version</dt>
          <dd className="text-mono">
            {promo.fromVersion || "—"} → {promo.toVersion}
          </dd>
          <dt>Strategy</dt>
          <dd>{promo.strategy}</dd>
          <dt>Status</dt>
          <dd>
            <span className={promotionStatusClass(promo.status)}>
              {promo.status}
            </span>
          </dd>
          <dt>Requested By</dt>
          <dd>{promo.requestedBy}</dd>
          <dt>Requested At</dt>
          <dd>{new Date(promo.requestedAt).toLocaleString()}</dd>
          {promo.approvedBy && (
            <>
              <dt>Approved By</dt>
              <dd>{promo.approvedBy}</dd>
            </>
          )}
          {promo.completedAt && (
            <>
              <dt>Completed</dt>
              <dd>{new Date(promo.completedAt).toLocaleString()}</dd>
            </>
          )}
          {promo.forceReason && (
            <>
              <dt>Force Reason</dt>
              <dd>{promo.forceReason}</dd>
            </>
          )}
          {promo.notes && (
            <>
              <dt>Notes</dt>
              <dd>{promo.notes}</dd>
            </>
          )}
        </dl>
      </div>

      <div className="detail-section">
        <h3>Gate Results</h3>
        {promo.gateResults.length === 0 ? (
          <p className="text-muted">No gate results yet.</p>
        ) : (
          <ul className="gate-timeline">
            {promo.gateResults.map((g, i) => (
              <li
                key={g.id || `${g.gateId}-${i}`}
                className={`gate-timeline-item ${
                  g.passed ? "passed" : "failed"
                }`}
              >
                <span className="gate-icon">{g.passed ? "✓" : "✗"}</span>
                <div className="gate-body">
                  <div className="gate-type">{g.gateType}</div>
                  {g.message && (
                    <div className="gate-message">{g.message}</div>
                  )}
                  <div className="gate-meta">
                    {new Date(g.evaluatedAt).toLocaleString()}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="detail-section">
        <h3>Actions</h3>
        <div className="btn-group">
          {canApprove && (
            <>
              <input
                type="text"
                placeholder="Optional approval notes"
                value={approveNotes}
                onChange={(e) => setApproveNotes(e.target.value)}
              />
              <button
                className="btn btn-primary"
                onClick={handleApprove}
                disabled={submitting}
              >
                Approve
              </button>
            </>
          )}
          {canReject && (
            <button className="btn btn-danger" onClick={() => setModal("reject")}>
              Reject
            </button>
          )}
          {canForce && (
            <button className="btn btn-danger" onClick={() => setModal("force")}>
              Force Push
            </button>
          )}
          {canRollback && (
            <button className="btn btn-danger" onClick={() => setModal("rollback")}>
              Rollback
            </button>
          )}
          {canCancel && (
            <button className="btn" onClick={handleCancel}>
              Cancel
            </button>
          )}
        </div>
      </div>

      {modal && (
        <div className="modal-backdrop" onClick={() => setModal(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>
              {modal === "reject"
                ? "Reject Promotion"
                : modal === "force"
                ? "Force Push Promotion"
                : "Rollback Promotion"}
            </h3>
            {modal === "force" && (
              <div className="alert alert-error">
                This bypasses gates. Reason will be captured in audit log.
              </div>
            )}
            <div className="form-group">
              <label>Reason</label>
              <input
                type="text"
                required
                value={modalReason}
                onChange={(e) => setModalReason(e.target.value)}
              />
            </div>
            <div className="btn-group">
              <button
                className="btn btn-primary"
                disabled={!modalReason.trim() || submitting}
                onClick={handleModalSubmit}
              >
                Confirm
              </button>
              <button className="btn" onClick={() => setModal(null)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
