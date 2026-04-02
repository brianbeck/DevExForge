import Keycloak from "keycloak-js";

interface RuntimeConfig {
  apiBaseUrl: string;
  keycloakUrl: string;
}

let _config: RuntimeConfig | null = null;

export async function loadConfig(): Promise<RuntimeConfig> {
  if (_config) return _config;

  try {
    const resp = await fetch("/config.json");
    if (resp.ok) {
      const json = await resp.json();
      if (json.apiBaseUrl) {
        _config = json as RuntimeConfig;
        return _config!;
      }
    }
  } catch {
    // Fall through to defaults
  }

  // Defaults for local development only
  const isLocal = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
  _config = {
    apiBaseUrl: import.meta.env.VITE_API_BASE_URL || (isLocal ? "http://localhost:8000" : ""),
    keycloakUrl: import.meta.env.VITE_KEYCLOAK_URL || (isLocal ? "http://localhost:8080" : ""),
  };
  return _config;
}

// Synchronous access after loadConfig() has been called
export function getConfig(): RuntimeConfig {
  if (!_config) {
    const isLocal = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
    return {
      apiBaseUrl: import.meta.env.VITE_API_BASE_URL || (isLocal ? "http://localhost:8000" : ""),
      keycloakUrl: import.meta.env.VITE_KEYCLOAK_URL || (isLocal ? "http://localhost:8080" : ""),
    };
  }
  return _config;
}

let _keycloak: Keycloak | null = null;

export function getKeycloak(): Keycloak {
  if (!_keycloak) {
    const cfg = getConfig();
    _keycloak = new Keycloak({
      url: cfg.keycloakUrl,
      realm: "teams",
      clientId: "devexforge-portal",
    });
  }
  return _keycloak;
}

// Keep API_BASE_URL export for backwards compatibility with local dev
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
