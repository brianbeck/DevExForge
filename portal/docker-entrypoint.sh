#!/bin/sh
API_BASE_URL="${API_BASE_URL:-}"
KEYCLOAK_URL="${KEYCLOAK_URL:-}"

cat > /usr/share/nginx/html/config.json <<EOF
{
  "apiBaseUrl": "${API_BASE_URL}",
  "keycloakUrl": "${KEYCLOAK_URL}"
}
EOF

chmod 644 /usr/share/nginx/html/config.json
echo "Runtime config written to /usr/share/nginx/html/config.json"
