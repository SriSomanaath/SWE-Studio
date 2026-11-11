#!/usr/bin/env node
// SWE Studio on AWS: EKS + Karpenter (CPU spot + GPU spot, scale to zero),
// EBS for API state, S3, ECR, IRSA. One stack so `cdk destroy` / scripts/teardown.sh
// removes everything in one go.
//
// Rough us-east-1 cost (on-demand list prices; spot varies, measured in Phase 6):
//   idle    ~ $0.24/h: EKS control plane 0.10 + 2x t3.medium 0.083 + NAT 0.045
//                      + 10 GiB gp3 ~0.001 + NAT public IPv4 0.005
//   running ~ $1/h:    idle + 1 GPU spot (g5/g6.xlarge ~0.35-0.50) + a few CPU
//                      spot nodes for agent Jobs (~0.03-0.08 each) + NAT data.
import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as ecr from "aws-cdk-lib/aws-ecr";
import * as eks from "aws-cdk-lib/aws-eks";
import * as events from "aws-cdk-lib/aws-events";
import * as targets from "aws-cdk-lib/aws-events-targets";
import * as iam from "aws-cdk-lib/aws-iam";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as sqs from "aws-cdk-lib/aws-sqs";
import { KubectlV35Layer } from "@aws-cdk/lambda-layer-kubectl-v35";

const KARPENTER_VERSION = "1.15.1";
const NAMESPACE = "swe-studio";

const app = new cdk.App();
const stack = new cdk.Stack(app, "SweStudio", {
  env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION ?? "us-east-1" },
});
const destroy = cdk.RemovalPolicy.DESTROY; // throwaway benchmark env: nothing survives teardown

// --- Network -----------------------------------------------------------------
// 2 AZs so spot has more capacity pools; 1 NAT gateway (not one per AZ) since
// an AZ outage during a benchmark is an acceptable risk for $0.045/h saved.
const vpc = new ec2.Vpc(stack, "Vpc", { maxAzs: 2, natGateways: 1 });

// --- EKS -----------------------------------------------------------------------
const cluster = new eks.Cluster(stack, "Cluster", {
  clusterName: "swe-studio",
  version: eks.KubernetesVersion.V1_35,
  kubectlLayer: new KubectlV35Layer(stack, "Kubectl"),
  vpc,
  vpcSubnets: [{ subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }],
  defaultCapacity: 0,
  authenticationMode: eks.AuthenticationMode.API_AND_CONFIG_MAP,
});

// Small always-on, on-demand group for things that must not be reclaimed:
// the API, Karpenter itself, CoreDNS. Everything elastic goes to Karpenter.
cluster.addNodegroupCapacity("System", {
  instanceTypes: [new ec2.InstanceType("t3.medium")],
  minSize: 2,
  maxSize: 2,
  capacityType: eks.CapacityType.ON_DEMAND,
});

// Let your own IAM identity run kubectl (pass ADMIN_PRINCIPAL_ARN at deploy;
// `aws sts get-caller-identity`). CDK's own kubectl role is admin already.
if (process.env.ADMIN_PRINCIPAL_ARN) {
  cluster.grantAccess("Admin", process.env.ADMIN_PRINCIPAL_ARN, [
    eks.AccessPolicy.fromAccessPolicyName("AmazonEKSClusterAdminPolicy", {
      accessScopeType: eks.AccessScopeType.CLUSTER,
    }),
  ]);
}

cluster.addManifest("Namespace", { apiVersion: "v1", kind: "Namespace", metadata: { name: NAMESPACE } });

// IRSA: a pod's ServiceAccount maps to an IAM role through the cluster's OIDC
// provider, so pods get scoped, short-lived AWS creds instead of the node's.
// CfnJson defers the issuer-keyed condition until the issuer URL is known.
function irsaRole(id: string, namespace: string, serviceAccount: string): iam.Role {
  const issuer = cluster.openIdConnectProvider.openIdConnectProviderIssuer;
  const conditions = new cdk.CfnJson(stack, `${id}Cond`, {
    value: {
      [`${issuer}:sub`]: `system:serviceaccount:${namespace}:${serviceAccount}`,
      [`${issuer}:aud`]: "sts.amazonaws.com",
    },
  });
  return new iam.Role(stack, id, {
    assumedBy: new iam.OpenIdConnectPrincipal(cluster.openIdConnectProvider).withConditions({
      StringEquals: conditions,
    }),
  });
}

// --- Storage + images ----------------------------------------------------------
const bucket = new s3.Bucket(stack, "Trajectories", {
  blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
  encryption: s3.BucketEncryption.S3_MANAGED,
  enforceSSL: true,
  removalPolicy: destroy,
  autoDeleteObjects: true, // otherwise teardown fails on a non-empty bucket
});

// One repo: the API and the agent runner are the same image with different
// commands (apps/api/Dockerfile), so a second repo would hold identical bytes.
const repo = new ecr.Repository(stack, "Repo", {
  repositoryName: "swe-studio",
  removalPolicy: destroy,
  emptyOnDelete: true,
});

// API state (SQLite index + .traj files) lives on one EBS gp3 volume.
// Postgres would allow >1 API replica, but the API only takes one /ingest per
// run, so it is not the bottleneck: the scale is in the runner Jobs. Durable
// copies of every trajectory go to S3 (app/routers/ingest.py).
const ebsCsiRole = irsaRole("EbsCsiRole", "kube-system", "ebs-csi-controller-sa");
ebsCsiRole.addManagedPolicy(
  iam.ManagedPolicy.fromAwsManagedPolicyName("service-role/AmazonEBSCSIDriverPolicy"),
);
const ebsCsi = new eks.CfnAddon(stack, "EbsCsi", {
  addonName: "aws-ebs-csi-driver",
  clusterName: cluster.clusterName,
  serviceAccountRoleArn: ebsCsiRole.roleArn,
});
cluster.addManifest("Gp3", {
  apiVersion: "storage.k8s.io/v1",
  kind: "StorageClass",
  // Default class, so deploy/k8s/api.yaml's PVC works unchanged on kind and EKS.
  metadata: { name: "gp3", annotations: { "storageclass.kubernetes.io/is-default-class": "true" } },
  provisioner: "ebs.csi.aws.com",
  // EBS volumes are single-AZ: wait until the pod is scheduled, then create
  // the volume in that pod's AZ.
  volumeBindingMode: "WaitForFirstConsumer",
  parameters: { type: "gp3", encrypted: "true" },
}).node.addDependency(ebsCsi);

// API pods: write-only to the trajectories bucket (it only mirrors ingests).
// Agent runners get NO AWS role on purpose: they run LLM-chosen shell, so they
// hold zero cloud credentials and ship results via the API's /ingest instead.
const apiRole = irsaRole("ApiRole", NAMESPACE, "swe-studio-api");
bucket.grantPut(apiRole);

// --- Karpenter -----------------------------------------------------------------
// Role assumed by the EC2 instances Karpenter launches.
const nodeRole = new iam.Role(stack, "KarpenterNodeRole", {
  assumedBy: new iam.ServicePrincipal("ec2.amazonaws.com"),
  managedPolicies: [
    "AmazonEKSWorkerNodePolicy",
    "AmazonEKS_CNI_Policy",
    "AmazonEC2ContainerRegistryReadOnly",
    "AmazonSSMManagedInstanceCore",
  ].map((n) => iam.ManagedPolicy.fromAwsManagedPolicyName(n)),
});
new eks.CfnAccessEntry(stack, "KarpenterNodeAccess", {
  clusterName: cluster.clusterName,
  principalArn: nodeRole.roleArn,
  type: "EC2_LINUX",
});

// Spot interruption handling: EC2 sends a 2-minute warning to EventBridge ->
// SQS; Karpenter reads it, cordons + drains the node and pre-launches a
// replacement before the instance disappears.
const queue = new sqs.Queue(stack, "KarpenterInterruptions", {
  retentionPeriod: cdk.Duration.minutes(5),
  enforceSSL: true,
  removalPolicy: destroy,
});
for (const [id, detailType, source] of [
  ["SpotInterruption", "EC2 Spot Instance Interruption Warning", "aws.ec2"],
  ["Rebalance", "EC2 Instance Rebalance Recommendation", "aws.ec2"],
  ["StateChange", "EC2 Instance State-change Notification", "aws.ec2"],
  ["ScheduledChange", "AWS Health Event", "aws.health"],
] as const) {
  new events.Rule(stack, id, {
    eventPattern: { source: [source], detailType: [detailType] },
    targets: [new targets.SqsQueue(queue)],
  });
}

const controllerRole = irsaRole("KarpenterControllerRole", "kube-system", "karpenter");
controllerRole.addToPolicy(
  new iam.PolicyStatement({
    actions: [
      "ec2:CreateFleet", "ec2:RunInstances", "ec2:CreateLaunchTemplate", "ec2:DeleteLaunchTemplate",
      "ec2:CreateTags", "ec2:DescribeAvailabilityZones", "ec2:DescribeImages", "ec2:DescribeInstances",
      "ec2:DescribeInstanceTypeOfferings", "ec2:DescribeInstanceTypes", "ec2:DescribeLaunchTemplates",
      "ec2:DescribeSecurityGroups", "ec2:DescribeSpotPriceHistory", "ec2:DescribeSubnets",
      "ec2:DescribeCapacityReservations", "pricing:GetProducts", "ssm:GetParameter",
      "iam:GetInstanceProfile", "iam:ListInstanceProfiles", "iam:CreateInstanceProfile",
      "iam:TagInstanceProfile", "iam:AddRoleToInstanceProfile", "iam:RemoveRoleFromInstanceProfile",
      "iam:DeleteInstanceProfile",
    ],
    resources: ["*"],
  }),
);
// Karpenter may only terminate instances it launched (it tags them).
controllerRole.addToPolicy(
  new iam.PolicyStatement({
    actions: ["ec2:TerminateInstances"],
    resources: ["*"],
    conditions: { StringLike: { "ec2:ResourceTag/karpenter.sh/nodepool": "*" } },
  }),
);
controllerRole.addToPolicy(
  new iam.PolicyStatement({ actions: ["iam:PassRole"], resources: [nodeRole.roleArn] }),
);
controllerRole.addToPolicy(
  new iam.PolicyStatement({ actions: ["eks:DescribeCluster"], resources: [cluster.clusterArn] }),
);
queue.grantConsumeMessages(controllerRole);

const karpenter = cluster.addHelmChart("Karpenter", {
  chart: "karpenter",
  repository: "oci://public.ecr.aws/karpenter/karpenter",
  version: KARPENTER_VERSION,
  namespace: "kube-system",
  release: "karpenter",
  wait: true,
  values: {
    replicas: 1, // 2 is the HA default; one controller is fine for a bench env
    serviceAccount: {
      name: "karpenter",
      annotations: { "eks.amazonaws.com/role-arn": controllerRole.roleArn },
    },
    settings: { clusterName: cluster.clusterName, interruptionQueue: queue.queueName },
  },
});

// GPU driver choice: EKS-optimized AL2023 NVIDIA AMI (driver + container
// toolkit baked in, Karpenter picks it automatically for GPU instance types)
// + the small NVIDIA device plugin DaemonSet. The GPU Operator would instead
// install the driver at boot inside a container (+ NFD, GFD, MIG manager...),
// adding minutes to every scale-from-zero cold start for features we don't use.
const devicePlugin = cluster.addHelmChart("NvidiaDevicePlugin", {
  chart: "nvidia-device-plugin",
  repository: "https://nvidia.github.io/k8s-device-plugin",
  version: "0.20.1",
  namespace: "kube-system",
  release: "nvidia-device-plugin",
  // Chart's default affinity needs NFD labels; our GPU NodePool sets
  // nvidia.com/gpu.present=true instead, which the chart also accepts.
});

const nodeClass = (name: string, rootGiB: number) => ({
  apiVersion: "karpenter.k8s.aws/v1",
  kind: "EC2NodeClass",
  metadata: { name },
  spec: {
    role: nodeRole.roleName,
    amiSelectorTerms: [{ alias: "al2023@latest" }],
    subnetSelectorTerms: vpc.privateSubnets.map((s) => ({ id: s.subnetId })),
    securityGroupSelectorTerms: [{ id: cluster.clusterSecurityGroupId }],
    blockDeviceMappings: [
      { deviceName: "/dev/xvda", ebs: { volumeSize: `${rootGiB}Gi`, volumeType: "gp3", deleteOnTermination: true } },
    ],
  },
});

const pools = cluster.addManifest(
  "KarpenterPools",
  nodeClass("cpu", 40),
  // vLLM image (~10 GiB) + model weights in emptyDir (~15 GiB) live on root.
  nodeClass("gpu", 120),
  {
    apiVersion: "karpenter.sh/v1",
    kind: "NodePool",
    metadata: { name: "cpu-spot" },
    spec: {
      template: {
        metadata: { labels: { "swe-studio/pool": "cpu" } },
        spec: {
          nodeClassRef: { group: "karpenter.k8s.aws", kind: "EC2NodeClass", name: "cpu" },
          requirements: [
            { key: "karpenter.sh/capacity-type", operator: "In", values: ["spot"] },
            { key: "kubernetes.io/arch", operator: "In", values: ["amd64"] },
            // Wide c/m/r families = many spot pools = fewer interruptions.
            { key: "karpenter.k8s.aws/instance-category", operator: "In", values: ["c", "m", "r"] },
            { key: "karpenter.k8s.aws/instance-generation", operator: "Gt", values: ["5"] },
          ],
          expireAfter: "24h",
        },
      },
      limits: { cpu: "64" }, // hard ceiling on agent fleet spend
      disruption: { consolidationPolicy: "WhenEmptyOrUnderutilized", consolidateAfter: "1m" },
    },
  },
  {
    apiVersion: "karpenter.sh/v1",
    kind: "NodePool",
    metadata: { name: "gpu-spot" },
    spec: {
      template: {
        metadata: { labels: { "swe-studio/pool": "gpu", "nvidia.com/gpu.present": "true" } },
        spec: {
          nodeClassRef: { group: "karpenter.k8s.aws", kind: "EC2NodeClass", name: "gpu" },
          requirements: [
            { key: "karpenter.sh/capacity-type", operator: "In", values: ["spot"] },
            // 1x A10G (g5) or 1x L4 (g6), 24 GiB each: fits a 7B model in bf16.
            { key: "node.kubernetes.io/instance-type", operator: "In", values: ["g5.xlarge", "g6.xlarge"] },
          ],
          // Only GPU workloads (which tolerate this) may land here.
          taints: [{ key: "nvidia.com/gpu", value: "true", effect: "NoSchedule" }],
          expireAfter: "24h",
        },
      },
      limits: { "nvidia.com/gpu": "2" },
      // Scale to zero: once vLLM is scaled to 0 the node is empty and is
      // removed after 5 min. Karpenter never removes a node that still runs
      // vLLM, so idling the model is `kubectl scale deploy/vllm --replicas=0`.
      disruption: { consolidationPolicy: "WhenEmpty", consolidateAfter: "5m" },
    },
  },
);
pools.node.addDependency(karpenter); // CRDs ship with the chart
devicePlugin.node.addDependency(karpenter);

new cdk.CfnOutput(stack, "Region", { value: stack.region });
new cdk.CfnOutput(stack, "ClusterName", { value: cluster.clusterName });
new cdk.CfnOutput(stack, "EcrRepo", { value: repo.repositoryUri });
new cdk.CfnOutput(stack, "Bucket", { value: bucket.bucketName });
new cdk.CfnOutput(stack, "ApiRoleArn", { value: apiRole.roleArn });
