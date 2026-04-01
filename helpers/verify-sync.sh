#!/bin/bash

# Count teams in API
API_TEAMS=$(curl -s http://localhost:8080/teams | jq 'length')

# Count operator-managed namespaces
K8S_NAMESPACES=$(kubectl get namespaces -l app.kubernetes.io/managed-by=teams-operator --no-headers | wc -l)

echo "Teams in API:     $API_TEAMS"
echo "K8s Namespaces:   $K8S_NAMESPACES"

if [ "$API_TEAMS" -eq "$K8S_NAMESPACES" ]; then
    echo "In sync"
else
    echo "Out of sync!"
fi

