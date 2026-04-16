import { useCallback, useEffect, useState } from "react";
import { useKeycloak } from "@react-keycloak/web";
import {
  listAllGates,
  createPlatformGate,
  deletePlatformGate,
} from "@/api/promotions";
import type {
  PromotionGate,
  PlatformGateCreate,
  Tier,
} from "@/api/promotions";

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

const GATE_TYPES = [
  "manual_approval",
  "image_signature",
  "vulnerability_scan",
  "test_results",
  "slo_check",
  "policy_check",
  "change_window",
  "dependency_check",
] as const;

type GateType = (typeof GATE_TYPES)[number];

export default function AdminGatesPage() {
  const { keycloak } = useKeycloak();
  const admin = isPlatformAdmin(
    keycloak.tokenParsed as Record<string, unknown> | undefined
  );

  const [gates, setGates] = useState<PromotionGate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tierFilter, setTierFilter] = useState<string>("");
  const [form, setForm] = useState<{
    gateType: GateType;
    tier: string;
    enforcement: "blocking" | "advisory";
    configJson: string;
  }>({
    gateType: "manual_approval",
    tier: "",
    enforcement: "blocking",
    configJson: "{}",
  });
  const [submitting, setSubmitting] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const data = await listAllGates(
        "platform",
        tierFilter || undefined
      );
      setGates(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load gates");
    } finally {
      setLoading(false);
    }
  }, [tierFilter]);

  useEffect(() => {
    if (admin) fetchData();
  }, [admin, fetchData]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      let config: Record<string, unknown> = {};
      if (form.configJson.trim()) {
        config = JSON.parse(form.configJson);
      }
      const body: PlatformGateCreate = {
        gateType: form.gateType,
        tier: (form.tier || null) as Tier | null,
        enforcement: form.enforcement,
        config,
      };
      await createPlatformGate(body);
      setForm({
        gateType: "manual_approval",
        tier: "",
        enforcement: "blocking",
        configJson: "{}",
      });
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create gate");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this gate?")) return;
    try {
      await deletePlatformGate(id);
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete");
    }
  }

  if (!admin) {
    return (
      <div className="page">
        <div className="alert alert-error">
          This view is restricted to platform administrators.
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="loading-screen">
        <p>Loading gates...</p>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Platform Promotion Gates</h2>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <form className="card form-card" onSubmit={handleCreate}>
        <h4>Create Platform Gate</h4>
        <div className="form-row">
          <div className="form-group">
            <label>Gate Type</label>
            <select
              value={form.gateType}
              onChange={(e) =>
                setForm({ ...form, gateType: e.target.value as GateType })
              }
            >
              {GATE_TYPES.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>Tier</label>
            <select
              value={form.tier}
              onChange={(e) => setForm({ ...form, tier: e.target.value })}
            >
              <option value="">(all)</option>
              <option value="dev">dev</option>
              <option value="staging">staging</option>
              <option value="production">production</option>
            </select>
          </div>
          <div className="form-group">
            <label>Enforcement</label>
            <select
              value={form.enforcement}
              onChange={(e) =>
                setForm({
                  ...form,
                  enforcement: e.target.value as "blocking" | "advisory",
                })
              }
            >
              <option value="blocking">blocking</option>
              <option value="advisory">advisory</option>
            </select>
          </div>
        </div>
        <div className="form-group">
          <label>Config (JSON)</label>
          <textarea
            rows={4}
            style={{
              padding: "8px 12px",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-sm)",
              fontFamily: "monospace",
              fontSize: "12px",
            }}
            value={form.configJson}
            onChange={(e) => setForm({ ...form, configJson: e.target.value })}
          />
        </div>
        <button
          className="btn btn-primary"
          type="submit"
          disabled={submitting}
        >
          {submitting ? "Creating..." : "Create Gate"}
        </button>
      </form>

      <div className="audit-filters">
        <select
          value={tierFilter}
          onChange={(e) => setTierFilter(e.target.value)}
        >
          <option value="">All tiers</option>
          <option value="dev">dev</option>
          <option value="staging">staging</option>
          <option value="production">production</option>
        </select>
      </div>

      {gates.length === 0 ? (
        <div className="empty-state">
          <p>No platform gates defined.</p>
        </div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Gate Type</th>
              <th>Tier</th>
              <th>Scope</th>
              <th>Enforcement</th>
              <th>Config</th>
              <th>Created By</th>
              <th>Created At</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {gates.map((g) => (
              <tr key={g.id}>
                <td>{g.gateType}</td>
                <td>{g.tier || "all"}</td>
                <td>{g.scope}</td>
                <td>{g.enforcement}</td>
                <td>
                  {g.config && Object.keys(g.config).length > 0 ? (
                    <pre className="gate-config-pre">
                      {JSON.stringify(g.config, null, 2)}
                    </pre>
                  ) : (
                    <span className="text-muted">—</span>
                  )}
                </td>
                <td>{g.createdBy}</td>
                <td>{new Date(g.createdAt).toLocaleString()}</td>
                <td>
                  <button
                    className="btn btn-sm btn-danger"
                    onClick={() => handleDelete(g.id)}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
