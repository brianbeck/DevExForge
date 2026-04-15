import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useKeycloak } from "@react-keycloak/web";
import { getGlobalInventory } from "@/api/applications";
import type { InventoryResponse } from "@/api/applications";
import { InventoryGrid } from "./ApplicationsPage";

function isPlatformAdmin(tokenParsed: Record<string, unknown> | undefined): boolean {
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

export default function GlobalInventoryPage() {
  const { keycloak } = useKeycloak();
  const navigate = useNavigate();
  const [inventory, setInventory] = useState<InventoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const admin = isPlatformAdmin(
    keycloak.tokenParsed as Record<string, unknown> | undefined
  );

  useEffect(() => {
    if (!admin) {
      setLoading(false);
      return;
    }
    async function fetchData() {
      try {
        setLoading(true);
        const data = await getGlobalInventory();
        setInventory(data);
        setError(null);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load inventory"
        );
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [admin]);

  if (!admin) {
    return (
      <div className="page">
        <div className="page-header">
          <h2>Applications</h2>
        </div>
        <div className="card">
          <h3>Access Denied</h3>
          <p className="text-muted">
            This view is restricted to platform administrators.
          </p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="loading-screen">
        <p>Loading global inventory...</p>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Applications (All Teams)</h2>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {!inventory || inventory.rows.length === 0 ? (
        <div className="empty-state">
          <p>No applications registered across any team.</p>
        </div>
      ) : (
        <InventoryGrid
          rows={inventory.rows}
          showTeam
          onTeamRowClick={(teamSlug, name) =>
            navigate(`/teams/${teamSlug}/applications/${name}`)
          }
        />
      )}
    </div>
  );
}
