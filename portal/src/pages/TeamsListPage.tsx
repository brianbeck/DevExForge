import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listTeams, createTeam } from "@/api/teams";
import type { Team, TeamCreate } from "@/types";

export default function TeamsListPage() {
  const navigate = useNavigate();
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<TeamCreate>({
    displayName: "",
    description: "",
    costCenter: "",
    tags: {},
  });
  const [tagKey, setTagKey] = useState("");
  const [tagValue, setTagValue] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function fetchTeams() {
    try {
      setLoading(true);
      const response = await listTeams();
      setTeams(response.teams);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load teams");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchTeams();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await createTeam(formData);
      setShowForm(false);
      setFormData({ displayName: "", description: "", costCenter: "", tags: {} });
      setTagKey("");
      setTagValue("");
      await fetchTeams();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create team");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <div className="loading-screen"><p>Loading teams...</p></div>;
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Teams</h2>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cancel" : "Create Team"}
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {showForm && (
        <form className="card form-card" onSubmit={handleCreate}>
          <h3>New Team</h3>
          <div className="form-group">
            <label htmlFor="displayName">Display Name</label>
            <input
              id="displayName"
              type="text"
              required
              placeholder="My Team"
              value={formData.displayName}
              onChange={(e) =>
                setFormData({ ...formData, displayName: e.target.value })
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="description">Description</label>
            <input
              id="description"
              type="text"
              placeholder="What does this team do?"
              value={formData.description || ""}
              onChange={(e) =>
                setFormData({ ...formData, description: e.target.value })
              }
            />
          </div>
          <div className="form-group">
            <label htmlFor="costCenter">Cost Center</label>
            <input
              id="costCenter"
              type="text"
              placeholder="CC-1234"
              value={formData.costCenter || ""}
              onChange={(e) =>
                setFormData({ ...formData, costCenter: e.target.value })
              }
            />
          </div>
          <div className="form-group">
            <label>Tags</label>
            <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
              <input
                type="text"
                placeholder="Key"
                value={tagKey}
                onChange={(e) => setTagKey(e.target.value)}
                style={{ flex: 1 }}
              />
              <input
                type="text"
                placeholder="Value"
                value={tagValue}
                onChange={(e) => setTagValue(e.target.value)}
                style={{ flex: 1 }}
              />
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => {
                  if (tagKey.trim()) {
                    setFormData({
                      ...formData,
                      tags: { ...(formData.tags || {}), [tagKey.trim()]: tagValue.trim() },
                    });
                    setTagKey("");
                    setTagValue("");
                  }
                }}
              >
                Add
              </button>
            </div>
            {formData.tags && Object.keys(formData.tags).length > 0 && (
              <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                {Object.entries(formData.tags).map(([k, v]) => (
                  <span
                    key={k}
                    className="badge"
                    style={{ cursor: "pointer" }}
                    onClick={() => {
                      const { [k]: _, ...rest } = formData.tags || {};
                      setFormData({ ...formData, tags: rest });
                    }}
                    title="Click to remove"
                  >
                    {k}: {v} &times;
                  </span>
                ))}
              </div>
            )}
          </div>
          <button className="btn btn-primary" type="submit" disabled={submitting}>
            {submitting ? "Creating..." : "Create"}
          </button>
        </form>
      )}

      {teams.length === 0 && !showForm ? (
        <div className="empty-state">
          <p>No teams yet. Create your first team to get started.</p>
        </div>
      ) : (
        <div className="card-grid">
          {teams.map((team) => (
            <div
              key={team.slug}
              className="card card-clickable"
              onClick={() => navigate(`/teams/${team.slug}`)}
            >
              <h3>{team.displayName}</h3>
              {team.description && (
                <p className="card-description">{team.description}</p>
              )}
              {team.tags && Object.keys(team.tags).length > 0 && (
                <div style={{ display: "flex", gap: "4px", flexWrap: "wrap", marginBottom: "8px" }}>
                  {Object.entries(team.tags).map(([k, v]) => (
                    <span key={k} className="badge badge-sm">{k}: {v}</span>
                  ))}
                </div>
              )}
              <div className="card-meta">
                <span>Owner: {team.ownerEmail}</span>
                <span>{team.memberCount} members</span>
                <span>{team.environmentCount} environments</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
