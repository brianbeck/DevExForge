import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ReactKeycloakProvider } from "@react-keycloak/web";
import { keycloakConfig } from "@/config";
import App from "@/App";

const initOptions = {
  onLoad: "check-sso" as const,
  silentCheckSsoRedirectUri:
    window.location.origin + "/silent-check-sso.html",
  pkceMethod: "S256" as const,
};

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ReactKeycloakProvider
      authClient={keycloakConfig}
      initOptions={initOptions}
      LoadingComponent={
        <div className="loading-screen">
          <p>Loading DevExForge...</p>
        </div>
      }
    >
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ReactKeycloakProvider>
  </React.StrictMode>
);
