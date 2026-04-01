#!/bin/bash
echo "=== CAPSTONE VERIFICATION ==="
kubectl get pods -n gatekeeper-system | grep Running
kubectl get pods -n falco-system | grep Running
kubectl get pods -n engineering-platform | grep Running
kubectl get ns -l app.kubernetes.io/managed-by=teams-operator
curl http://localhost:8000/health
echo "\n"
