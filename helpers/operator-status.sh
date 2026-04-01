#!/bin/bash

echo "====== TEAMS OPERATOR STATUS ======"
echo ""
# Operator pod status
echo "Operator Pod:"
kubectl get pods -n engineering-platform -l app=teams-operator
echo ""
echo "Teams in API:"
curl -s http://localhost:8080/teams | jq 'length'
echo ""
echo "Managed Namespaces:"
kubectl get namespaces -l app.kubernetes.io/managed-by=teams-operator --no-headers | wc -l
echo ""
echo "Recent Operator Activity:"
kubectl logs -n engineering-platform deployment/teams-operator --tail=10
echo ""
echo "===================================="

