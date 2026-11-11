#!/usr/bin/env bash
# Destroy everything up.sh created: AWS_PROFILE=x CONFIRM_ACCOUNT=123456789012 scripts/teardown.sh
# Karpenter's EC2 instances are NOT CloudFormation resources, so they must be
# drained first; otherwise `cdk destroy` hangs on the VPC (their ENIs) and the
# instances keep billing.
set -uo pipefail
source "$(dirname "$0")/_aws_guard.sh"

# Keep the benchmark's trajectories: the bucket is deleted with the stack.
BUCKET=$(aws cloudformation describe-stacks --stack-name SweStudio \
  --query "Stacks[0].Outputs[?OutputKey=='Bucket'].OutputValue" --output text 2>/dev/null)
if [ -n "$BUCKET" ] && [ "$BUCKET" != None ]; then
  DEST="$ROOT/bench-results/trajectories"
  aws s3 sync "s3://$BUCKET" "$DEST" || { echo "S3 backup failed; aborting before deleting anything" >&2; exit 1; }
  echo "trajectories saved to $DEST"
fi

if aws eks update-kubeconfig --name "$CLUSTER" --region "$AWS_REGION" >/dev/null 2>&1; then
  kubectl delete namespace swe-studio --wait --timeout=5m          # vLLM + runner Jobs
  kubectl delete nodepools.karpenter.sh --all --wait --timeout=10m  # Karpenter terminates its nodes
  kubectl delete ec2nodeclasses.karpenter.k8s.aws --all --wait --timeout=5m
fi

# Safety net: anything Karpenter launched that still exists.
IDS=$(aws ec2 describe-instances \
  --filters "Name=tag-key,Values=karpenter.sh/nodepool" "Name=tag-key,Values=kubernetes.io/cluster/$CLUSTER" \
            "Name=instance-state-name,Values=pending,running,stopping,stopped" \
  --query 'Reservations[].Instances[].InstanceId' --output text)
[ -n "$IDS" ] && aws ec2 terminate-instances --instance-ids $IDS >/dev/null && \
  aws ec2 wait instance-terminated --instance-ids $IDS

cd "$ROOT/infra" && npx cdk destroy --force

echo "--- leftovers (should all be empty) ---"
aws eks list-clusters --query 'clusters' --output text
aws ec2 describe-instances --filters "Name=tag-key,Values=kubernetes.io/cluster/$CLUSTER" \
  "Name=instance-state-name,Values=pending,running" --query 'Reservations[].Instances[].InstanceId' --output text
aws ec2 describe-nat-gateways --filter "Name=state,Values=available" --query 'NatGateways[].NatGatewayId' --output text
aws ec2 describe-volumes --filters "Name=tag:kubernetes.io/created-for/pvc/namespace,Values=swe-studio" \
  --query 'Volumes[].VolumeId' --output text
aws ecr describe-repositories --repository-names swe-studio >/dev/null 2>&1 && echo "ECR repo still exists"
