import Keycloak from "keycloak-js";

export const keycloakConfig = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL || "https://keycloak.brianbeck.net",
  realm: "teams",
  clientId: "devexforge-portal",
});

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "/api";
