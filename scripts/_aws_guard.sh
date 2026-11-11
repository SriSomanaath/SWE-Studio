# Sourced by up.sh / teardown.sh. Refuses to touch AWS unless the profile is
# named explicitly AND the account it resolves to is confirmed, so a default
# profile pointing at some other account can never be used by accident.
: "${AWS_PROFILE:?set AWS_PROFILE explicitly (e.g. AWS_PROFILE=personal)}"
: "${CONFIRM_ACCOUNT:?set CONFIRM_ACCOUNT=<12-digit account id> you intend to use}"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
[ "$ACCOUNT" = "$CONFIRM_ACCOUNT" ] || { echo "profile $AWS_PROFILE is account $ACCOUNT, not $CONFIRM_ACCOUNT" >&2; exit 1; }
export AWS_REGION="${AWS_REGION:-us-east-1}" CDK_DEFAULT_REGION="${AWS_REGION:-us-east-1}" CDK_DEFAULT_ACCOUNT="$ACCOUNT"
ROOT=$(cd "$(dirname "$0")/.." && pwd)
CLUSTER=swe-studio
