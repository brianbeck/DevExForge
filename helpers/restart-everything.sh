#~/bin/sh
#

FOUNDATION=/home/beck/src/pe-architect-course/workshop/foundation
CVE=/home/beck/src/pe-architect-course/workshop/capoc/cve
QUALITY=/home/beck/src/pe-architect-course/workshop/capoc/quality
SECOPS=/home/beck/src/pe-architect-course/workshop/secops
API=/home/beck/src/pe-architect-course/workshop/teams-management/teams-api
OPERATOR=/home/beck/src/pe-architect-course/workshop/teams-management/teams-operator
KEYCLOAK=/home/beck/src/pe-architect-course/workshop/teams-management/keycloak

kubectl create namespace monitoring

helm install grafana-stack prometheus-community/kube-prometheus-stack \
	  --namespace monitoring \
	    --values $FOUNDATION/grafana-stack-values.yaml \
	      --wait

kubectl apply -f https://raw.githubusercontent.com/open-policy-agent/gatekeeper/release-3.14/deploy/gatekeeper.yaml

kubectl wait --for=condition=Ready pod -l control-plane=controller-manager -n gatekeeper-system --timeout=90s

kubectl apply -f $FOUNDATION/simple-constraint-template.yaml
kubectl apply -f $FOUNDATION/simple-constraint.yaml

helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
helm repo update

helm upgrade --install metrics-server metrics-server/metrics-server \
	  --namespace kube-system \
	    --set args={--kubelet-insecure-tls}

kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=metrics-server -n kube-system --timeout=90s

#CVE
kubectl apply -f $CVE/cve-constraint-template.yaml
kubectl apply -f $QUALITY/cve-constraint.yaml

#Quality
kubectl apply -f $QUALITY/quality-constraint-template.yaml
kubectl apply -f $QUALITY/quality-constraint.yaml

#SECOPS

# Add the Falco Helm repository
helm repo add falcosecurity https://falcosecurity.github.io/charts
helm repo update


#Install Falco with eBPF driver and gRPC output
helm install falco falcosecurity/falco \
	  --namespace falco-system \
	    --create-namespace \
	      --set driver.kind=modern_ebpf \
	        --set falcosidekick.enabled=true


# Create custom rule file and deploy with Falco
 helm upgrade falco falcosecurity/falco \
   --namespace falco-system \
     --set driver.kind=modern_ebpf \
       --set falcosidekick.enabled=true \
         --set-file customRules."custom_rules\.yaml"=$SECOPS/root-detect-rule.yaml

# Apply security constraint template
kubectl apply -f $SECOPS/constraint-template.yaml
# Apply security constraint
kubectl apply -f $SECOPS/constraint.yaml

kubectl create namespace engineering-platform
kubectl apply -f $API/deployment.yaml

#Operator
kubectl apply -f $OPERATOR/operator-deployment.yaml

#Keycloak
kubectl apply -f $KEYCLOAK/keycloak.yaml

