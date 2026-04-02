import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ReactKeycloakProvider } from "@react-keycloak/web";
import { loadConfig, getKeycloak } from "@/config";
import App from "@/App";

const initOptions = {
  onLoad: "check-sso" as const,
  pkceMethod: "S256" as const,
};

// Load runtime config before initializing Keycloak
loadConfig().then(() => {
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <ReactKeycloakProvider
        authClient={getKeycloak()}
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
});
