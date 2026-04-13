from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://devexforge:devexforge@localhost:5432/devexforge"
    KEYCLOAK_URL: str = "http://localhost:8080"
    KEYCLOAK_ISSUER_URL: str = ""
    KEYCLOAK_REALM: str = "teams"
    KEYCLOAK_CLIENT_ID: str = "devexforge-api"
    K8S_IN_CLUSTER: bool = False
    K8S_CRD_GROUP: str = "devexforge.brianbeck.net"
    K8S_CRD_VERSION: str = "v1alpha1"
    K8S_STAGE_CONTEXT: str = ""
    K8S_PROD_CONTEXT: str = ""
    TIER_CLUSTER_MAP: dict[str, str] = {"dev": "beck-stage", "staging": "beck-stage", "production": "beck-prod"}
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    PROMETHEUS_STAGE_URL: str = ""
    PROMETHEUS_PROD_URL: str = ""
    GRAFANA_STAGE_URL: str = ""
    GRAFANA_PROD_URL: str = ""

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}


settings = Settings()
