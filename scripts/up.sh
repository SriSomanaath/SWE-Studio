#!/usr/bin/env bash
# Bring up the whole stack: AWS_PROFILE=x CONFIRM_ACCOUNT=123456789012 \
#   ANTHROPIC_API_KEY=... [MOONSHOT_API_KEY=...] [WITH_GPU=1] scripts/up.sh
# Costs money from the moment it starts; scripts/teardown.sh removes it all.
set -euo pipefail
source "$(dirname "$0")/_aws_guard.sh"

out() { aws cloudformation describe-stacks --stack-name SweStudio \
  --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }

cd "$ROOT/infra" && npm ci --no-audit --no-fund
npx cdk bootstrap "aws://$ACCOUNT/$AWS_REGION"
ADMIN_PRINCIPAL_ARN=$(aws sts get-caller-identity --query Arn --output text | \
  sed -E 's#:sts::([0-9]+):assumed-role/([^/]+)/.*#:iam::\1:role/\2#') \
  npx cdk deploy --require-approval never
aws eks update-kubeconfig --name "$CLUSTER" --region "$AWS_REGION"

# Nodes are x86_64; build for amd64 even from an arm Mac. Unique tag so
# IfNotPresent never reuses a stale image.
REPO=$(out EcrRepo); TAG=$(date +%s)
aws ecr get-login-password | docker login --username AWS --password-stdin "${REPO%%/*}"
docker buildx build --platform linux/amd64 -t "$REPO:$TAG" --push "$ROOT/apps/api"

k() { kubectl -n swe-studio "$@"; }
kubectl apply -f "$ROOT/deploy/k8s/base.yaml"
k annotate sa swe-studio-api --overwrite "eks.amazonaws.com/role-arn=$(out ApiRoleArn)"

KEY=$(openssl rand -hex 16)
k create secret generic swe-studio-api --from-literal=API_KEYS="$KEY" --dry-run=client -o yaml | kubectl apply -f -
k create secret generic swe-studio-runner --from-literal=STUDIO_API_KEY="$KEY" \
  ${ANTHROPIC_API_KEY:+--from-literal=ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY"} \
  ${MOONSHOT_API_KEY:+--from-literal=MOONSHOT_API_KEY="$MOONSHOT_API_KEY"} \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f "$ROOT/deploy/k8s/api.yaml"
k set image deploy/swe-studio-api api="$REPO:$TAG"
k set env deploy/swe-studio-api RUNNER_IMAGE="$REPO:$TAG" RUNNER_POOL=cpu TRAJECTORIES_BUCKET="$(out Bucket)"
# API stays on the on-demand system nodes: a spot reclaim must not take it down.
k patch deploy/swe-studio-api -p '{"spec":{"template":{"spec":{"nodeSelector":{"eks.amazonaws.com/capacityType":"ON_DEMAND"}}}}}'
k rollout status deploy/swe-studio-api --timeout=5m

# Monitoring: Prometheus + Grafana (+ DCGM GPU exporter with WITH_GPU=1).
MON="$ROOT/deploy/k8s/monitoring"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null
helm repo add dcgm https://nvidia.github.io/dcgm-exporter/helm-charts >/dev/null
helm repo update prometheus-community dcgm >/dev/null
GRAFANA_PW=$(openssl rand -hex 12)
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack --version 93.2.0 \
  -n monitoring --create-namespace -f "$MON/kube-prometheus-stack.yaml" \
  --set grafana.adminPassword="$GRAFANA_PW" --wait --timeout 10m
kubectl apply -f "$MON/servicemonitors.yaml"
kubectl -n monitoring create configmap swe-studio-dashboard \
  --from-file=swe-studio.json="$MON/dashboard.json" --dry-run=client -o yaml | \
  kubectl label --local -f - grafana_dashboard=1 -o yaml | kubectl apply -f -

if [ "${WITH_GPU:-0}" = 1 ]; then
  helm upgrade --install dcgm-exporter dcgm/dcgm-exporter --version 4.9.0 \
    -n monitoring -f "$MON/dcgm-exporter.yaml"
  kubectl apply -f "$ROOT/deploy/k8s/vllm/vllm.yaml"
  echo "vLLM: Karpenter is launching a GPU node; first start takes ~10 min (k get pods -w)."
fi
echo "API key: $KEY   ->  kubectl -n swe-studio port-forward svc/swe-studio-api 8080"
echo "Grafana: admin / $GRAFANA_PW  ->  kubectl -n monitoring port-forward svc/monitoring-grafana 3001:80"
