import { useKeycloak } from "@react-keycloak/web";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { keycloak, initialized } = useKeycloak();

  if (!initialized) {
    return (
      <div className="loading-screen">
        <p>Initializing authentication...</p>
      </div>
    );
  }

  if (!keycloak.authenticated) {
    keycloak.login();
    return (
      <div className="loading-screen">
        <p>Redirecting to login...</p>
      </div>
    );
  }

  return <>{children}</>;
}
