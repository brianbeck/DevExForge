import { useEffect, useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import { listMembers, addMember, updateMember, removeMember } from "@/api/members";
import type { Member, MemberCreate } from "@/types";

type MemberRole = "admin" | "developer" | "viewer";
const ROLES: MemberRole[] = ["admin", "developer", "viewer"];

export default function MembersPage() {
  const { slug } = useParams<{ slug: string }>();
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<MemberCreate>({
    email: "",
    role: "developer",
  });
  const [submitting, setSubmitting] = useState(false);

  const fetchMembers = useCallback(async () => {
    if (!slug) return;
    try {
      setLoading(true);
      const data = await listMembers(slug);
      setMembers(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load members");
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    fetchMembers();
  }, [fetchMembers]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!slug) return;
    setSubmitting(true);
    try {
      await addMember(slug, formData);
      setShowForm(false);
      setFormData({ email: "", role: "developer" });
      await fetchMembers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add member");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRoleChange(memberEmail: string, newRole: string) {
    if (!slug) return;
    try {
      await updateMember(slug, memberEmail, newRole);
      await fetchMembers();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to update role"
      );
    }
  }

  async function handleRemove(member: Member) {
    if (!slug) return;
    const confirmed = window.confirm(
      `Remove ${member.email} from the team?`
    );
    if (!confirmed) return;
    try {
      await removeMember(slug, member.email);
      await fetchMembers();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to remove member"
      );
    }
  }

  if (loading) {
    return <div className="loading-screen"><p>Loading members...</p></div>;
  }

  return (
    <div>
      <div className="section-header">
        <h3>Members</h3>
        <button
          className="btn btn-primary"
          onClick={() => setShowForm(!showForm)}
        >
          {showForm ? "Cancel" : "Add Member"}
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {showForm && (
        <form className="card form-card" onSubmit={handleAdd}>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                required
                placeholder="user@example.com"
                value={formData.email}
                onChange={(e) =>
                  setFormData({ ...formData, email: e.target.value })
                }
              />
            </div>
            <div className="form-group">
              <label htmlFor="role">Role</label>
              <select
                id="role"
                value={formData.role}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    role: e.target.value as MemberRole,
                  })
                }
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
            <button
              className="btn btn-primary form-btn"
              type="submit"
              disabled={submitting}
            >
              {submitting ? "Adding..." : "Add"}
            </button>
          </div>
        </form>
      )}

      {members.length === 0 ? (
        <div className="empty-state">
          <p>No members found.</p>
        </div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Role</th>
              <th>Added</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {members.map((member) => (
              <tr key={member.email}>
                <td>{member.email}</td>
                <td>
                  <select
                    value={member.role}
                    onChange={(e) =>
                      handleRoleChange(member.email, e.target.value)
                    }
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                </td>
                <td>{new Date(member.addedAt).toLocaleDateString()}</td>
                <td>
                  <button
                    className="btn btn-sm btn-danger"
                    onClick={() => handleRemove(member)}
                  >
                    Remove
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
