from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["system", "user", "assistant", "tool", "Action Summary"]


class HistoryMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    role: Role | str
    content: str = ""
    action: str | None = None
    is_demo: bool | None = None


class TrajectoryStep(BaseModel):
    model_config = ConfigDict(extra="allow")
    thought: str = ""
    action: str = ""
    response: str = ""
    observation: str = ""
    messages: list[dict[str, Any]] = Field(default_factory=list)


class ModelStats(BaseModel):
    model_config = ConfigDict(extra="allow")
    instance_cost: float | None = None
    tokens_sent: int | None = None
    tokens_received: int | None = None
    api_calls: int | None = None


class RunInfo(BaseModel):
    model_config = ConfigDict(extra="allow")
    exit_status: str | None = None
    submission: str | None = None
    model_stats: ModelStats = Field(default_factory=ModelStats)


class TrajectoryFile(BaseModel):
    """The raw `.traj` JSON the agent writes out."""

    model_config = ConfigDict(extra="allow")
    history: list[HistoryMessage] = Field(default_factory=list)
    trajectory: list[TrajectoryStep] = Field(default_factory=list)
    info: RunInfo = Field(default_factory=RunInfo)


class EvalStatus(BaseModel):
    """benchmark-style evaluation status, sourced from sibling results.json."""

    completed: bool | None = None
    submitted: bool | None = None
    resolved: bool | None = None


class TrajectorySummary(BaseModel):
    """Lightweight view for list pages — no step content."""

    id: str
    run_id: str
    relative_path: str
    exit_status: str | None = None
    api_calls: int | None = None
    instance_cost: float | None = None
    tokens_sent: int | None = None
    tokens_received: int | None = None
    step_count: int = 0
    eval: EvalStatus = Field(default_factory=EvalStatus)


class TrajectoryDetail(BaseModel):
    """Full step-by-step view served to the trajectory page."""

    id: str
    run_id: str
    relative_path: str
    problem_statement: str | None = None
    steps: list[TrajectoryStep]
    info: RunInfo
    eval: EvalStatus = Field(default_factory=EvalStatus)


class RunSummary(BaseModel):
    id: str
    relative_path: str
    trajectory_count: int
    resolved_count: int | None = None
    submitted_count: int | None = None
    has_results: bool


class RunStats(BaseModel):
    """Aggregate metrics across all trajectories in a run."""

    trajectory_count: int
    resolved_count: int
    submitted_count: int
    completed_count: int
    pass_rate: float | None  # resolved / completed (None if no eval)

    total_cost: float
    mean_cost: float | None
    median_cost: float | None

    total_tokens_sent: int
    total_tokens_received: int
    total_api_calls: int

    median_step_count: float | None
    p95_step_count: float | None

    exit_status_counts: dict[str, int]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    trajectories_dir: str
    trajectories_dir_exists: bool


class LiveTrajectory(BaseModel):
    run_id: str
    trajectory_id: str
    mtime: float
    step_count: int
    exit_status: str | None = None
    eval: EvalStatus = Field(default_factory=EvalStatus)


class CompareSide(BaseModel):
    run_id: str
    trajectory_id: str


class CompareSummary(BaseModel):
    step_count_a: int
    step_count_b: int
    step_count_delta: int  # b - a
    cost_a: float | None
    cost_b: float | None
    cost_delta: float | None  # b - a
    api_calls_a: int | None
    api_calls_b: int | None
    eval_resolved_a: bool | None
    eval_resolved_b: bool | None
    action_overlap_ratio: float  # |actions(a) ∩ actions(b)| / |union|


class CompareResult(BaseModel):
    a: TrajectoryDetail
    b: TrajectoryDetail
    summary: CompareSummary
    diff_analysis: "DiffAnalysis | None" = None


class HistogramBin(BaseModel):
    label: str
    count: int
    lower: float | None = None
    upper: float | None = None


class BucketPassRate(BaseModel):
    label: str
    total: int
    resolved: int
    rate: float | None


class TopTrajectory(BaseModel):
    id: str
    instance_cost: float | None = None
    step_count: int = 0
    api_calls: int | None = None
    exit_status: str | None = None
    eval_resolved: bool | None = None


class ExitStatusBreakdown(BaseModel):
    exit_status: str
    total: int
    resolved: int


class RunAnalytics(BaseModel):
    """Aggregations served to the analytics dashboard."""

    cost_histogram: list[HistogramBin]
    step_histogram: list[HistogramBin]
    pass_rate_by_step_bucket: list[BucketPassRate]
    exit_status_breakdown: list[ExitStatusBreakdown]
    top_costly: list[TopTrajectory]
    top_longest: list[TopTrajectory]


class InstanceSide(BaseModel):
    present: bool
    eval_resolved: bool | None = None
    eval_submitted: bool | None = None
    eval_completed: bool | None = None
    exit_status: str | None = None
    instance_cost: float | None = None
    step_count: int | None = None


class InstanceCompareRow(BaseModel):
    id: str
    in_a: InstanceSide
    in_b: InstanceSide
    divergent: bool
    cost_delta: float | None = None


class RunCompareSummary(BaseModel):
    a_id: str
    b_id: str
    instances_in_a_only: int
    instances_in_b_only: int
    instances_in_both: int
    resolved_only_a: int
    resolved_only_b: int
    resolved_in_both: int
    failed_in_both: int
    divergent_count: int
    total_cost_a: float
    total_cost_b: float
    cost_delta: float


class RunCompareResult(BaseModel):
    summary: RunCompareSummary
    instances: list[InstanceCompareRow]


# --- Phase 5: annotations + bookmarks ---


class Annotation(BaseModel):
    id: int
    run_id: str
    trajectory_id: str
    step_index: int  # -1 means trajectory-level
    author: str
    body: str
    created_at: float
    updated_at: float


class AnnotationCreate(BaseModel):
    step_index: int = -1
    body: str

    @classmethod
    def model_validate(cls, data, **kwargs):
        return super().model_validate(data, **kwargs)


class AnnotationUpdate(BaseModel):
    body: str


class Bookmark(BaseModel):
    run_id: str
    trajectory_id: str
    author: str
    note: str | None = None
    created_at: float


class BookmarkCreate(BaseModel):
    note: str | None = None


class IngestResult(BaseModel):
    status: Literal["accepted"] = "accepted"
    run_id: str
    trajectory_id: str
    file_path: str


# --- Phase 6: search + diff intelligence ---


class SearchHit(BaseModel):
    kind: Literal["trajectory", "annotation"]
    run_id: str
    trajectory_id: str
    step_index: int | None = None
    field: str  # "problem", "step_text", "instance_id", "annotation_body"
    snippet: str
    score: float  # FTS5 bm25 (lower = better)


class SearchResult(BaseModel):
    query: str
    hits: list[SearchHit]
    total: int


class DiffFileStat(BaseModel):
    path: str
    in_a: bool
    in_b: bool
    added_a: int = 0
    removed_a: int = 0
    added_b: int = 0
    removed_b: int = 0


class DiffAnalysis(BaseModel):
    files_a_count: int
    files_b_count: int
    files_in_both: int
    files_only_a: int
    files_only_b: int
    file_overlap_ratio: float
    files: list[DiffFileStat]


# --- Phase 7: showcase ---


class ShowcaseEntry(BaseModel):
    slug: str
    run_id: str
    trajectory_id: str
    title: str
    description: str | None = None
    pinned_step: int | None = None
    author: str
    created_at: float
    updated_at: float


class ShowcaseCreate(BaseModel):
    slug: str
    run_id: str
    trajectory_id: str
    title: str
    description: str | None = None
    pinned_step: int | None = None


class ShowcaseUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    pinned_step: int | None = None


# --- Phase 8: AI summaries ---


SummaryProvider = Literal["heuristic", "ai"]


class AISummary(BaseModel):
    """Generated summary of a trajectory. Distinct from the list-row schema
    `TrajectorySummary` defined above for `/runs/{r}/trajectories`."""

    run_id: str
    trajectory_id: str
    provider: SummaryProvider
    body: str
    model: str | None = None
    created_at: float
    cached: bool = False


# --- Phase 9: insights + similarity ---


class TrajectoryCluster(BaseModel):
    fingerprint: str  # e.g. "ls·grep·sed" — the top-3 action verbs joined
    size: int
    resolved_count: int
    submitted_count: int
    failed_count: int
    median_step_count: float | None
    mean_cost: float | None
    sample_ids: list[str]


class RunInsights(BaseModel):
    run_id: str
    trajectory_count: int
    clusters: list[TrajectoryCluster]


class SimilarHit(BaseModel):
    run_id: str
    trajectory_id: str
    score: float  # negative bm25 — higher = more similar
    snippet: str


# --- Phase 10: webhooks ---


WebhookEvent = Literal[
    "trajectory.completed",
    "trajectory.resolved",
    "trajectory.updated",
    "summary.generated",
    "bookmark.created",
    "showcase.created",
]


class Webhook(BaseModel):
    id: int
    url: str
    events: list[str]  # empty list = subscribe to all
    secret: str
    active: bool
    description: str | None = None
    created_at: float


class WebhookCreate(BaseModel):
    url: str
    events: list[str] = []
    description: str | None = None


class WebhookUpdate(BaseModel):
    url: str | None = None
    events: list[str] | None = None
    active: bool | None = None
    description: str | None = None


class WebhookDelivery(BaseModel):
    id: int
    webhook_id: int
    event: str
    payload: str
    status_code: int | None = None
    success: bool
    attempts: int
    error: str | None = None
    created_at: float


# --- Phase 11: shares + embeddings ---


ShareKind = Literal["run", "trajectory", "showcase"]


class Share(BaseModel):
    token: str
    kind: ShareKind
    target_run_id: str | None = None
    target_traj_id: str | None = None
    target_slug: str | None = None
    description: str | None = None
    author: str
    created_at: float
    expires_at: float | None = None
    revoked: bool = False
    url: str | None = None


class ShareCreate(BaseModel):
    kind: ShareKind
    run_id: str | None = None
    trajectory_id: str | None = None
    slug: str | None = None
    description: str | None = None
    ttl_seconds: int | None = None


class ResolvedShare(BaseModel):
    """What the public `/s/{token}` route uses to render the target."""

    token: str
    kind: ShareKind
    expires_at: float | None = None
    description: str | None = None
    target_run_id: str | None = None
    target_traj_id: str | None = None
    target_slug: str | None = None


class EmbeddingsStatus(BaseModel):
    available: bool
    model: str
    indexed_count: int
    reason: str | None = None


# --- Phase 13: workspaces + auth ---


class Workspace(BaseModel):
    id: str
    name: str
    description: str | None = None
    created_at: float


class WorkspaceCreate(BaseModel):
    id: str
    name: str
    description: str | None = None


class User(BaseModel):
    id: str
    name: str | None = None
    email: str | None = None
    created_at: float


class WorkspaceMember(BaseModel):
    workspace_id: str
    user_id: str
    role: str
    created_at: float


class CurrentUser(BaseModel):
    """`GET /me` — describes the caller's identity + workspaces."""

    user: User | None = None
    workspaces: list[Workspace]
    active_workspace_id: str


class Viewer(BaseModel):
    user_id: str
    name: str | None = None
    step_index: int | None = None
    last_seen: float


class PresenceState(BaseModel):
    run_id: str
    trajectory_id: str
    viewers: list[Viewer]


class ReplayResult(BaseModel):
    new_run_id: str
    trajectory_id: str
    events_url: str
    step_count: int


class AgentRunRequest(BaseModel):
    problem: str
    repo: str  # absolute path to a working directory
    model: str = "claude-sonnet-4-5"
    run_id: str | None = None
    trajectory_id: str | None = None
    max_steps: int = 30
    max_cost_usd: float = 5.0


class AgentRunAccepted(BaseModel):
    run_id: str
    trajectory_id: str
    file_path: str
    events_url: str
    trajectory_url: str


class AgentEnsembleRequest(BaseModel):
    problem: str
    repo: str
    models: list[str]
    max_steps: int = 30
    max_cost_usd: float = 5.0
    docker_image: str | None = None


class AgentEnsembleAccepted(BaseModel):
    run_id: str
    trajectories: list[AgentRunAccepted]
    compare_url: str | None = None
