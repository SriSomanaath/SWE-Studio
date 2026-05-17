import { z } from "zod";

export const modelStatsSchema = z
  .object({
    instance_cost: z.number().nullable().optional(),
    tokens_sent: z.number().int().nullable().optional(),
    tokens_received: z.number().int().nullable().optional(),
    api_calls: z.number().int().nullable().optional(),
  })
  .passthrough();

export const evalStatusSchema = z.object({
  completed: z.boolean().nullable().optional(),
  submitted: z.boolean().nullable().optional(),
  resolved: z.boolean().nullable().optional(),
});

export const runSummarySchema = z.object({
  id: z.string(),
  relative_path: z.string(),
  trajectory_count: z.number().int(),
  resolved_count: z.number().int().nullable().optional(),
  submitted_count: z.number().int().nullable().optional(),
  has_results: z.boolean(),
});

export const trajectorySummarySchema = z.object({
  id: z.string(),
  run_id: z.string(),
  relative_path: z.string(),
  exit_status: z.string().nullable().optional(),
  api_calls: z.number().int().nullable().optional(),
  instance_cost: z.number().nullable().optional(),
  tokens_sent: z.number().int().nullable().optional(),
  tokens_received: z.number().int().nullable().optional(),
  step_count: z.number().int(),
  eval: evalStatusSchema,
});

export const trajectoryStepSchema = z
  .object({
    thought: z.string().default(""),
    action: z.string().default(""),
    response: z.string().default(""),
    observation: z.string().default(""),
    messages: z.array(z.record(z.unknown())).default([]),
  })
  .passthrough();

export const runInfoSchema = z
  .object({
    exit_status: z.string().nullable().optional(),
    submission: z.string().nullable().optional(),
    model_stats: modelStatsSchema.default({}),
  })
  .passthrough();

export const trajectoryDetailSchema = z.object({
  id: z.string(),
  run_id: z.string(),
  relative_path: z.string(),
  problem_statement: z.string().nullable().optional(),
  steps: z.array(trajectoryStepSchema),
  info: runInfoSchema,
  eval: evalStatusSchema,
});

export const liveTrajectorySchema = z.object({
  run_id: z.string(),
  trajectory_id: z.string(),
  mtime: z.number(),
  step_count: z.number().int(),
  exit_status: z.string().nullable().optional(),
  eval: evalStatusSchema,
});

export const compareSummarySchema = z.object({
  step_count_a: z.number().int(),
  step_count_b: z.number().int(),
  step_count_delta: z.number().int(),
  cost_a: z.number().nullable(),
  cost_b: z.number().nullable(),
  cost_delta: z.number().nullable(),
  api_calls_a: z.number().int().nullable(),
  api_calls_b: z.number().int().nullable(),
  eval_resolved_a: z.boolean().nullable(),
  eval_resolved_b: z.boolean().nullable(),
  action_overlap_ratio: z.number(),
});

export const compareResultSchema = z.object({
  a: trajectoryDetailSchema,
  b: trajectoryDetailSchema,
  summary: compareSummarySchema,
  diff_analysis: z
    .object({
      files_a_count: z.number().int(),
      files_b_count: z.number().int(),
      files_in_both: z.number().int(),
      files_only_a: z.number().int(),
      files_only_b: z.number().int(),
      file_overlap_ratio: z.number(),
      files: z.array(
        z.object({
          path: z.string(),
          in_a: z.boolean(),
          in_b: z.boolean(),
          added_a: z.number().int(),
          removed_a: z.number().int(),
          added_b: z.number().int(),
          removed_b: z.number().int(),
        }),
      ),
    })
    .nullable()
    .optional(),
});

export const histogramBinSchema = z.object({
  label: z.string(),
  count: z.number().int(),
  lower: z.number().nullable().optional(),
  upper: z.number().nullable().optional(),
});

export const bucketPassRateSchema = z.object({
  label: z.string(),
  total: z.number().int(),
  resolved: z.number().int(),
  rate: z.number().nullable(),
});

export const topTrajectorySchema = z.object({
  id: z.string(),
  instance_cost: z.number().nullable().optional(),
  step_count: z.number().int(),
  api_calls: z.number().int().nullable().optional(),
  exit_status: z.string().nullable().optional(),
  eval_resolved: z.boolean().nullable().optional(),
});

export const exitStatusBreakdownSchema = z.object({
  exit_status: z.string(),
  total: z.number().int(),
  resolved: z.number().int(),
});

export const runAnalyticsSchema = z.object({
  cost_histogram: z.array(histogramBinSchema),
  step_histogram: z.array(histogramBinSchema),
  pass_rate_by_step_bucket: z.array(bucketPassRateSchema),
  exit_status_breakdown: z.array(exitStatusBreakdownSchema),
  top_costly: z.array(topTrajectorySchema),
  top_longest: z.array(topTrajectorySchema),
});

export const instanceSideSchema = z.object({
  present: z.boolean(),
  eval_resolved: z.boolean().nullable().optional(),
  eval_submitted: z.boolean().nullable().optional(),
  eval_completed: z.boolean().nullable().optional(),
  exit_status: z.string().nullable().optional(),
  instance_cost: z.number().nullable().optional(),
  step_count: z.number().int().nullable().optional(),
});

export const instanceCompareRowSchema = z.object({
  id: z.string(),
  in_a: instanceSideSchema,
  in_b: instanceSideSchema,
  divergent: z.boolean(),
  cost_delta: z.number().nullable().optional(),
});

export const runCompareSummarySchema = z.object({
  a_id: z.string(),
  b_id: z.string(),
  instances_in_a_only: z.number().int(),
  instances_in_b_only: z.number().int(),
  instances_in_both: z.number().int(),
  resolved_only_a: z.number().int(),
  resolved_only_b: z.number().int(),
  resolved_in_both: z.number().int(),
  failed_in_both: z.number().int(),
  divergent_count: z.number().int(),
  total_cost_a: z.number(),
  total_cost_b: z.number(),
  cost_delta: z.number(),
});

export const runCompareResultSchema = z.object({
  summary: runCompareSummarySchema,
  instances: z.array(instanceCompareRowSchema),
});

export const annotationSchema = z.object({
  id: z.number().int(),
  run_id: z.string(),
  trajectory_id: z.string(),
  step_index: z.number().int(),
  author: z.string(),
  body: z.string(),
  created_at: z.number(),
  updated_at: z.number(),
});

export const bookmarkSchema = z.object({
  run_id: z.string(),
  trajectory_id: z.string(),
  author: z.string(),
  note: z.string().nullable().optional(),
  created_at: z.number(),
});

export const searchHitSchema = z.object({
  kind: z.union([z.literal("trajectory"), z.literal("annotation")]),
  run_id: z.string(),
  trajectory_id: z.string(),
  step_index: z.number().int().nullable().optional(),
  field: z.string(),
  snippet: z.string(),
  score: z.number(),
});

export const searchResultSchema = z.object({
  query: z.string(),
  hits: z.array(searchHitSchema),
  total: z.number().int(),
});

export const diffFileStatSchema = z.object({
  path: z.string(),
  in_a: z.boolean(),
  in_b: z.boolean(),
  added_a: z.number().int(),
  removed_a: z.number().int(),
  added_b: z.number().int(),
  removed_b: z.number().int(),
});

export const diffAnalysisSchema = z.object({
  files_a_count: z.number().int(),
  files_b_count: z.number().int(),
  files_in_both: z.number().int(),
  files_only_a: z.number().int(),
  files_only_b: z.number().int(),
  file_overlap_ratio: z.number(),
  files: z.array(diffFileStatSchema),
});

export const trajectoryClusterSchema = z.object({
  fingerprint: z.string(),
  size: z.number().int(),
  resolved_count: z.number().int(),
  submitted_count: z.number().int(),
  failed_count: z.number().int(),
  median_step_count: z.number().nullable(),
  mean_cost: z.number().nullable(),
  sample_ids: z.array(z.string()),
});

export const runInsightsSchema = z.object({
  run_id: z.string(),
  trajectory_count: z.number().int(),
  clusters: z.array(trajectoryClusterSchema),
});

export const similarHitSchema = z.object({
  run_id: z.string(),
  trajectory_id: z.string(),
  score: z.number(),
  snippet: z.string(),
});

export const datasetManifestSchema = z.object({
  studio_version: z.string(),
  generated_at: z.string(),
  run_id: z.string(),
  record_count: z.number().int(),
  format: z.string(),
  schema_version: z.number().int(),
  stats: z.object({
    resolved_count: z.number().int(),
    submitted_count: z.number().int(),
    pass_rate: z.number().nullable(),
    total_cost_usd: z.number(),
    total_steps: z.number().int(),
  }),
  instances: z.array(z.record(z.unknown())),
  schema_fields: z.array(z.string()),
});

export const shareKindSchema = z.union([
  z.literal("run"),
  z.literal("trajectory"),
  z.literal("showcase"),
]);

export const shareSchema = z.object({
  token: z.string(),
  kind: shareKindSchema,
  target_run_id: z.string().nullable().optional(),
  target_traj_id: z.string().nullable().optional(),
  target_slug: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  author: z.string(),
  created_at: z.number(),
  expires_at: z.number().nullable().optional(),
  revoked: z.boolean(),
  url: z.string().nullable().optional(),
});

export const resolvedShareSchema = z.object({
  token: z.string(),
  kind: shareKindSchema,
  expires_at: z.number().nullable().optional(),
  description: z.string().nullable().optional(),
  target_run_id: z.string().nullable().optional(),
  target_traj_id: z.string().nullable().optional(),
  target_slug: z.string().nullable().optional(),
});

export const embeddingsStatusSchema = z.object({
  available: z.boolean(),
  model: z.string(),
  indexed_count: z.number().int(),
  reason: z.string().nullable().optional(),
});

export const webhookSchema = z.object({
  id: z.number().int(),
  url: z.string(),
  events: z.array(z.string()),
  secret: z.string(),
  active: z.boolean(),
  description: z.string().nullable().optional(),
  created_at: z.number(),
});

export const webhookDeliverySchema = z.object({
  id: z.number().int(),
  webhook_id: z.number().int(),
  event: z.string(),
  payload: z.string(),
  status_code: z.number().int().nullable().optional(),
  success: z.boolean(),
  attempts: z.number().int(),
  error: z.string().nullable().optional(),
  created_at: z.number(),
});

export const showcaseEntrySchema = z.object({
  slug: z.string(),
  run_id: z.string(),
  trajectory_id: z.string(),
  title: z.string(),
  description: z.string().nullable().optional(),
  pinned_step: z.number().int().nullable().optional(),
  author: z.string(),
  created_at: z.number(),
  updated_at: z.number(),
});

export const runStatsSchema = z.object({
  trajectory_count: z.number().int(),
  resolved_count: z.number().int(),
  submitted_count: z.number().int(),
  completed_count: z.number().int(),
  pass_rate: z.number().nullable(),
  total_cost: z.number(),
  mean_cost: z.number().nullable(),
  median_cost: z.number().nullable(),
  total_tokens_sent: z.number().int(),
  total_tokens_received: z.number().int(),
  total_api_calls: z.number().int(),
  median_step_count: z.number().nullable(),
  p95_step_count: z.number().nullable(),
  exit_status_counts: z.record(z.number().int()),
});

export type RunSummary = z.infer<typeof runSummarySchema>;
export type TrajectorySummary = z.infer<typeof trajectorySummarySchema>;
export type TrajectoryStep = z.infer<typeof trajectoryStepSchema>;
export type TrajectoryDetail = z.infer<typeof trajectoryDetailSchema>;
export type RunInfo = z.infer<typeof runInfoSchema>;
export type EvalStatus = z.infer<typeof evalStatusSchema>;
export type RunStats = z.infer<typeof runStatsSchema>;
export type LiveTrajectory = z.infer<typeof liveTrajectorySchema>;
export type CompareSummary = z.infer<typeof compareSummarySchema>;
export type CompareResult = z.infer<typeof compareResultSchema>;
export type HistogramBin = z.infer<typeof histogramBinSchema>;
export type BucketPassRate = z.infer<typeof bucketPassRateSchema>;
export type TopTrajectory = z.infer<typeof topTrajectorySchema>;
export type ExitStatusBreakdown = z.infer<typeof exitStatusBreakdownSchema>;
export type RunAnalytics = z.infer<typeof runAnalyticsSchema>;
export type InstanceSide = z.infer<typeof instanceSideSchema>;
export type InstanceCompareRow = z.infer<typeof instanceCompareRowSchema>;
export type RunCompareSummary = z.infer<typeof runCompareSummarySchema>;
export type RunCompareResult = z.infer<typeof runCompareResultSchema>;
export type Annotation = z.infer<typeof annotationSchema>;
export type Bookmark = z.infer<typeof bookmarkSchema>;
export type SearchHit = z.infer<typeof searchHitSchema>;
export type SearchResult = z.infer<typeof searchResultSchema>;
export type DiffFileStat = z.infer<typeof diffFileStatSchema>;
export type DiffAnalysis = z.infer<typeof diffAnalysisSchema>;
export type ShowcaseEntry = z.infer<typeof showcaseEntrySchema>;
export type TrajectoryCluster = z.infer<typeof trajectoryClusterSchema>;
export type RunInsights = z.infer<typeof runInsightsSchema>;
export type SimilarHit = z.infer<typeof similarHitSchema>;
export type DatasetManifest = z.infer<typeof datasetManifestSchema>;
export type Webhook = z.infer<typeof webhookSchema>;
export type WebhookDelivery = z.infer<typeof webhookDeliverySchema>;
export type Share = z.infer<typeof shareSchema>;
export type ResolvedShare = z.infer<typeof resolvedShareSchema>;
export type EmbeddingsStatusInfo = z.infer<typeof embeddingsStatusSchema>;

export type StatusFilter = "any" | "resolved" | "submitted" | "failed" | "unscored";
export type SortField = "id" | "instance_cost" | "api_calls" | "step_count" | "tokens_sent";
export type SortOrder = "asc" | "desc";

export interface TrajectoryFilters {
  status: StatusFilter;
  exit: string;
  search: string;
  costMin: string;
  costMax: string;
  sort: SortField;
  order: SortOrder;
}

export const DEFAULT_FILTERS: TrajectoryFilters = {
  status: "any",
  exit: "",
  search: "",
  costMin: "",
  costMax: "",
  sort: "id",
  order: "asc",
};
