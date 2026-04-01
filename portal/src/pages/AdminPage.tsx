import { useEffect, useState } from "react";
import {
  listQuotaPresets,
  createQuotaPreset,
  deleteQuotaPreset,
  listPolicyProfiles,
  createPolicyProfile,
  deletePolicyProfile,
} from "@/api/admin";
import type { QuotaPreset, PolicyProfile } from "@/api/admin";

type Tab = "quotas" | "policies";

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("quotas");
  const [quotas, setQuotas] = useState<QuotaPreset[]>([]);
  const [policies, setPolicies] = useState<PolicyProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showQuotaForm, setShowQuotaForm] = useState(false);
  const [showPolicyForm, setShowPolicyForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [quotaForm, setQuotaForm] = useState({
    name: "",
    cpuRequest: "500m",
    cpuLimit: "1",
    memoryRequest: "512Mi",
    memoryLimit: "1Gi",
    pods: 20,
    services: 10,
    pvcs: 5,
  });

  const [policyForm, setPolicyForm] = useState({
    name: "",
    maxCriticalCVEs: 0,
    maxHighCVEs: 5,
    requireNonRoot: true,
    requireReadOnlyRoot: false,
    requireResourceLimits: true,
  });

  async function fetchData() {
    try {
      setLoading(true);
      const [q, p] = await Promise.all([
        listQuotaPresets(),
        listPolicyProfiles(),
      ]);
      setQuotas(q);
      setPolicies(p);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load admin data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchData();
  }, []);

  async function handleCreateQuota(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await createQuotaPreset(quotaForm);
      setShowQuotaForm(false);
      setQuotaForm({
        name: "",
        cpuRequest: "500m",
        cpuLimit: "1",
        memoryRequest: "512Mi",
        memoryLimit: "1Gi",
        pods: 20,
        services: 10,
        pvcs: 5,
      });
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create preset");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeleteQuota(id: string) {
    if (!confirm("Delete this quota preset?")) return;
    try {
      await deleteQuotaPreset(id);
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete preset");
    }
  }

  async function handleCreatePolicy(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await createPolicyProfile(policyForm);
      setShowPolicyForm(false);
      setPolicyForm({
        name: "",
        maxCriticalCVEs: 0,
        maxHighCVEs: 5,
        requireNonRoot: true,
        requireReadOnlyRoot: false,
        requireResourceLimits: true,
      });
      await fetchData();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create profile"
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeletePolicy(id: string) {
    if (!confirm("Delete this policy profile?")) return;
    try {
      await deletePolicyProfile(id);
      await fetchData();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to delete profile"
      );
    }
  }

  if (loading) {
    return (
      <div className="loading-screen">
        <p>Loading admin data...</p>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Admin</h2>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="tab-nav">
        <button
          className={`tab${tab === "quotas" ? " active" : ""}`}
          onClick={() => setTab("quotas")}
        >
          Quota Presets
        </button>
        <button
          className={`tab${tab === "policies" ? " active" : ""}`}
          onClick={() => setTab("policies")}
        >
          Policy Profiles
        </button>
      </div>

      {tab === "quotas" && (
        <div className="admin-section">
          <div className="section-header">
            <h3>Quota Presets</h3>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => setShowQuotaForm(!showQuotaForm)}
            >
              {showQuotaForm ? "Cancel" : "Create Preset"}
            </button>
          </div>

          {showQuotaForm && (
            <form
              className="admin-form"
              onSubmit={handleCreateQuota}
            >
              <label>
                Name
                <input
                  type="text"
                  required
                  value={quotaForm.name}
                  onChange={(e) =>
                    setQuotaForm({ ...quotaForm, name: e.target.value })
                  }
                />
              </label>
              <label>
                CPU Request
                <input
                  type="text"
                  required
                  value={quotaForm.cpuRequest}
                  onChange={(e) =>
                    setQuotaForm({ ...quotaForm, cpuRequest: e.target.value })
                  }
                />
              </label>
              <label>
                CPU Limit
                <input
                  type="text"
                  required
                  value={quotaForm.cpuLimit}
                  onChange={(e) =>
                    setQuotaForm({ ...quotaForm, cpuLimit: e.target.value })
                  }
                />
              </label>
              <label>
                Memory Request
                <input
                  type="text"
                  required
                  value={quotaForm.memoryRequest}
                  onChange={(e) =>
                    setQuotaForm({
                      ...quotaForm,
                      memoryRequest: e.target.value,
                    })
                  }
                />
              </label>
              <label>
                Memory Limit
                <input
                  type="text"
                  required
                  value={quotaForm.memoryLimit}
                  onChange={(e) =>
                    setQuotaForm({
                      ...quotaForm,
                      memoryLimit: e.target.value,
                    })
                  }
                />
              </label>
              <label>
                Pods
                <input
                  type="number"
                  required
                  value={quotaForm.pods}
                  onChange={(e) =>
                    setQuotaForm({
                      ...quotaForm,
                      pods: parseInt(e.target.value, 10),
                    })
                  }
                />
              </label>
              <label>
                Services
                <input
                  type="number"
                  required
                  value={quotaForm.services}
                  onChange={(e) =>
                    setQuotaForm({
                      ...quotaForm,
                      services: parseInt(e.target.value, 10),
                    })
                  }
                />
              </label>
              <label>
                PVCs
                <input
                  type="number"
                  required
                  value={quotaForm.pvcs}
                  onChange={(e) =>
                    setQuotaForm({
                      ...quotaForm,
                      pvcs: parseInt(e.target.value, 10),
                    })
                  }
                />
              </label>
              <div style={{ gridColumn: "1 / -1" }}>
                <button
                  className="btn btn-primary"
                  type="submit"
                  disabled={submitting}
                >
                  {submitting ? "Creating..." : "Create"}
                </button>
              </div>
            </form>
          )}

          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>CPU Req</th>
                <th>CPU Limit</th>
                <th>Mem Req</th>
                <th>Mem Limit</th>
                <th>Pods</th>
                <th>Services</th>
                <th>PVCs</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {quotas.length === 0 ? (
                <tr>
                  <td colSpan={9} className="text-muted" style={{ textAlign: "center" }}>
                    No quota presets defined.
                  </td>
                </tr>
              ) : (
                quotas.map((q) => (
                  <tr key={q.id}>
                    <td>{q.name}</td>
                    <td className="text-mono">{q.cpuRequest}</td>
                    <td className="text-mono">{q.cpuLimit}</td>
                    <td className="text-mono">{q.memoryRequest}</td>
                    <td className="text-mono">{q.memoryLimit}</td>
                    <td>{q.pods}</td>
                    <td>{q.services}</td>
                    <td>{q.pvcs}</td>
                    <td>
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => handleDeleteQuota(q.id)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === "policies" && (
        <div className="admin-section">
          <div className="section-header">
            <h3>Policy Profiles</h3>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => setShowPolicyForm(!showPolicyForm)}
            >
              {showPolicyForm ? "Cancel" : "Create Profile"}
            </button>
          </div>

          {showPolicyForm && (
            <form
              className="admin-form"
              onSubmit={handleCreatePolicy}
            >
              <label>
                Name
                <input
                  type="text"
                  required
                  value={policyForm.name}
                  onChange={(e) =>
                    setPolicyForm({ ...policyForm, name: e.target.value })
                  }
                />
              </label>
              <label>
                Max Critical CVEs
                <input
                  type="number"
                  required
                  value={policyForm.maxCriticalCVEs}
                  onChange={(e) =>
                    setPolicyForm({
                      ...policyForm,
                      maxCriticalCVEs: parseInt(e.target.value, 10),
                    })
                  }
                />
              </label>
              <label>
                Max High CVEs
                <input
                  type="number"
                  required
                  value={policyForm.maxHighCVEs}
                  onChange={(e) =>
                    setPolicyForm({
                      ...policyForm,
                      maxHighCVEs: parseInt(e.target.value, 10),
                    })
                  }
                />
              </label>
              <label style={{ flexDirection: "row", alignItems: "center", gap: "0.5rem" }}>
                <input
                  type="checkbox"
                  checked={policyForm.requireNonRoot}
                  onChange={(e) =>
                    setPolicyForm({
                      ...policyForm,
                      requireNonRoot: e.target.checked,
                    })
                  }
                />
                Require Non-Root
              </label>
              <label style={{ flexDirection: "row", alignItems: "center", gap: "0.5rem" }}>
                <input
                  type="checkbox"
                  checked={policyForm.requireReadOnlyRoot}
                  onChange={(e) =>
                    setPolicyForm({
                      ...policyForm,
                      requireReadOnlyRoot: e.target.checked,
                    })
                  }
                />
                Require Read-Only Root
              </label>
              <label style={{ flexDirection: "row", alignItems: "center", gap: "0.5rem" }}>
                <input
                  type="checkbox"
                  checked={policyForm.requireResourceLimits}
                  onChange={(e) =>
                    setPolicyForm({
                      ...policyForm,
                      requireResourceLimits: e.target.checked,
                    })
                  }
                />
                Require Resource Limits
              </label>
              <div style={{ gridColumn: "1 / -1" }}>
                <button
                  className="btn btn-primary"
                  type="submit"
                  disabled={submitting}
                >
                  {submitting ? "Creating..." : "Create"}
                </button>
              </div>
            </form>
          )}

          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Max Critical</th>
                <th>Max High</th>
                <th>Non-Root</th>
                <th>RO Root</th>
                <th>Limits</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {policies.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-muted" style={{ textAlign: "center" }}>
                    No policy profiles defined.
                  </td>
                </tr>
              ) : (
                policies.map((p) => (
                  <tr key={p.id}>
                    <td>{p.name}</td>
                    <td>{p.maxCriticalCVEs}</td>
                    <td>{p.maxHighCVEs}</td>
                    <td>{p.requireNonRoot ? "Yes" : "No"}</td>
                    <td>{p.requireReadOnlyRoot ? "Yes" : "No"}</td>
                    <td>{p.requireResourceLimits ? "Yes" : "No"}</td>
                    <td>
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => handleDeletePolicy(p.id)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
