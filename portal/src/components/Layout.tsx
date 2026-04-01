import { NavLink, Outlet } from "react-router-dom";
import { useKeycloak } from "@react-keycloak/web";

export default function Layout() {
  const { keycloak } = useKeycloak();

  const userEmail =
    keycloak.tokenParsed?.email ||
    keycloak.tokenParsed?.preferred_username ||
    "User";

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <h1>DevExForge</h1>
        </div>
        <nav className="sidebar-nav">
          <NavLink
            to="/teams"
            className={({ isActive }) =>
              `nav-link${isActive ? " active" : ""}`
            }
          >
            <span className="nav-icon">&#9776;</span>
            Teams
          </NavLink>
          <NavLink
            to="/catalog"
            className={({ isActive }) =>
              `nav-link${isActive ? " active" : ""}`
            }
          >
            <span className="nav-icon">&#9733;</span>
            Catalog
          </NavLink>
          <NavLink
            to="/admin"
            className={({ isActive }) =>
              `nav-link${isActive ? " active" : ""}`
            }
          >
            <span className="nav-icon">&#9881;</span>
            Admin
          </NavLink>
          <NavLink
            to="/audit"
            className={({ isActive }) =>
              `nav-link${isActive ? " active" : ""}`
            }
          >
            <span className="nav-icon">&#9783;</span>
            Audit Log
          </NavLink>
        </nav>
      </aside>
      <div className="main-wrapper">
        <header className="topbar">
          <div className="topbar-spacer" />
          <div className="topbar-user">
            <span className="user-email">{userEmail}</span>
            <button
              className="btn btn-sm"
              onClick={() => keycloak.logout()}
            >
              Logout
            </button>
          </div>
        </header>
        <main className="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
