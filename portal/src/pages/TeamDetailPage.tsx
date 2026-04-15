import { useEffect, useState } from "react";
import { useParams, NavLink, Outlet, useLocation } from "react-router-dom";
import { getTeam } from "@/api/teams";
import { listEnvironments } from "@/api/environments";
import type { Team, Environment } from "@/types";

function TeamOverview({
  team,
  environments,
}: {
  team: Team;
  environments: Environment[];
}) {
  return (
    <div>
      <div className="detail-section">
        <h3>Team Info</h3>
        <dl className="detail-grid">
          <dt>Display Name</dt>
          <dd>{team.displayName}</dd>
          <dt>Description</dt>
          <dd>{team.description || "No description"}</dd>
          <dt>Owner</dt>
          <dd>{team.ownerEmail}</dd>
          <dt>Cost Center</dt>
          <dd>{team.costCenter || "Not set"}</dd>
          <dt>Created</dt>
          <dd>{new Date(team.createdAt).toLocaleDateString()}</dd>
        </dl>
        {team.tags && Object.keys(team.tags).length > 0 && (
          <div className="tags-list">
            {Object.entries(team.tags).map(([key, value]) => (
              <span key={key} className="tag">
                {key}: {value}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="detail-section">
        <h3>Environments</h3>
        {environments.length === 0 ? (
          <p className="text-muted">No environments provisioned yet.</p>
        ) : (
          <div className="card-grid">
            {environments.map((env) => (
              <div key={env.id} className="card card-sm">
                <div className="card-header-row">
                  <span className={`badge badge-tier-${env.tier}`}>
                    {env.tier}
                  </span>
                  <span className={`badge badge-phase-${env.phase}`}>
                    {env.phase}
                  </span>
                </div>
                <p className="text-mono">{env.namespaceName}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function TeamDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const location = useLocation();
  const [team, setTeam] = useState<Team | null>(null);
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isRootPath =
    location.pathname === `/teams/${slug}` ||
    location.pathname === `/teams/${slug}/`;

  useEffect(() => {
    if (!slug) return;
    async function fetchData() {
      try {
        setLoading(true);
        const [teamData, envData] = await Promise.all([
          getTeam(slug!),
          listEnvironments(slug!),
        ]);
        setTeam(teamData);
        setEnvironments(envData);
        setError(null);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load team"
        );
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [slug]);

  if (loading) {
    return <div className="loading-screen"><p>Loading team...</p></div>;
  }

  if (error || !team) {
    return (
      <div className="page">
        <div className="alert alert-error">{error || "Team not found"}</div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>{team.displayName}</h2>
      </div>

      <div className="tab-nav">
        <NavLink
          to={`/teams/${slug}`}
          end
          className={({ isActive }) => `tab${isActive ? " active" : ""}`}
        >
          Overview
        </NavLink>
        <NavLink
          to={`/teams/${slug}/members`}
          className={({ isActive }) => `tab${isActive ? " active" : ""}`}
        >
          Members
        </NavLink>
        <NavLink
          to={`/teams/${slug}/environments`}
          className={({ isActive }) => `tab${isActive ? " active" : ""}`}
        >
          Environments
        </NavLink>
        <NavLink
          to={`/teams/${slug}/applications`}
          className={({ isActive }) => `tab${isActive ? " active" : ""}`}
        >
          Applications
        </NavLink>
      </div>

      {isRootPath ? (
        <TeamOverview team={team} environments={environments} />
      ) : (
        <Outlet />
      )}
    </div>
  );
}
