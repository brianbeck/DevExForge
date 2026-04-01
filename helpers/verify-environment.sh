#!/bin/sh

#Verify Namespaces
echo "\nVerifying Namespaces (monitoring|gatekeeper|falco-system|teams-api|engineering-platform)-----------------"
kubectl get namespaces | grep -E "(monitoring|gatekeeper-system|falco-system|teams-api|engineering-platform)"

#Verify all monitoring pods are running
echo "\nVerifying Monitoring Pods -----------------"
kubectl get pods -n monitoring

#Verify gatekeeper pods are running
echo "\nVerifying Gatekeeper Pods -----------------"
kubectl get pods -n gatekeeper-system

#Verify Falco pods are running and monitoring
echo "\nVerifying Falco Pods -----------------"
kubectl get pods -n falco-system
echo "\nVerifying Falco is Monitoring -----------------"
kubectl get daemonset -n falco-system

#Verify platform-engineering  pods are running
echo "\nVerifying Platform Engineering Pods -----------------"
kubectl get pods -n engineering-platform

#Verify Contraint Templates
echo "\nVerifying Contraint Templates -------------------"
kubectl get constrainttemplates

#Verify Contraints
echo "\nVerifying Contraints -------------------"
kubectl get constraints

#Verify Namespaces with Managed By Attribute Set to "teams-operator"
echo "\nVerifying Namespaces with Managed by Attribute set to teams-operator  -------------------"
kubectl get ns -l app.kubernetes.io/managed-by=teams-operator

echo "\nCluster Info ----------------------"
kubectl cluster-info

echo "\nkubectl top -------------------------"
kubectl top nodes

