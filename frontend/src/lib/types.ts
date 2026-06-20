// DTOs mirroring the FastAPI backend contract.
//
// Sources of truth (read directly, fields are NOT invented):
//  - api/schemas.py            -> ProjectOut, JobOut
//  - api/routers/reads.py      -> ClusterOut, ScoreOut/CandidateOut, WorkOut/WorkDetailOut
//  - api/routers/search.py    + lacuna/pipeline/live_single_title.py -> LiveSearchCounts
//  - lacuna/export/context_pack.py -> ContextPack and friends (search job's `counts.pack`)
//
// The frontend never talks to anything but NEXT_PUBLIC_API_BASE — these types describe
// exactly what that backend returns, no more.

// ---------------------------------------------------------------------------
// Projects (api/schemas.py: ProjectOut)
// ---------------------------------------------------------------------------

export interface ProjectOut {
  id: string;
  name: string;
  target_bisac: string[];
  subject_filter: Record<string, unknown>;
  seeded: boolean;
  work_count: number;
  cluster_count: number;
  created_at: string | null;
}

// ---------------------------------------------------------------------------
// Jobs (api/schemas.py: JobOut)
// ---------------------------------------------------------------------------

export type JobStatus = "queued" | "running" | "done" | "error";

export interface JobOut {
  id: string;
  project_id: string | null;
  kind: string;
  status: JobStatus;
  progress_pct: number;
  step: string | null;
  counts: Record<string, unknown> | null;
  result_ref: string | null;
  error_detail: string | null;
  // api/jobs.py._row_to_dict also serializes these timestamps (not in the
  // Pydantic JobOut model, but present on every real response).
  created_at?: string | null;
  updated_at?: string | null;
}

// ---------------------------------------------------------------------------
// Context Pack (lacuna/export/context_pack.py) — carried in a live-search
// job's counts.pack, and returned verbatim by GET /projects/{id}/export.
// ---------------------------------------------------------------------------

export interface ComplaintOut {
  aspect: string;
  reviewer_count: number;
  helpful_weight: number;
  platforms: string[];
  cross_platform: boolean;
}

export interface CandidateJsonOut {
  ref: string;
  title_or_subject: string;
  gap_score: number;
  components: {
    demand: number;
    supply_scarcity: number;
    unmet_need: number;
  };
  validity: {
    confidence: number;
    sample_size: number;
    platforms: string[];
    oldest_signal: string | null;
    newest_signal: string | null;
    incomplete: boolean;
    blind_spot: boolean;
    recent_supply_surge: boolean;
  };
  top_complaints: ComplaintOut[];
  demand_evidence: Record<string, unknown>;
}

export interface ContextPack {
  legend: unknown;
  instructions_to_model: unknown;
  known_limitations: unknown;
  target: {
    project: string;
    bisac: string[];
    mode: string;
  };
  generated_at: string;
  provenance: {
    platforms_used: string[];
    total_reviews: number;
    cross_platform_agreement_pct: number;
  };
  candidates: CandidateJsonOut[];
}

// ---------------------------------------------------------------------------
// Live search job counts (api/routers/search.py start_search ->
// lacuna/pipeline/live_single_title.analyze_live). This is the dict stored in
// JobOut.counts for kind === "live_search" once status === "done".
// ---------------------------------------------------------------------------

export interface LiveSearchClusterOut {
  label: string;
  representative: string;
  reviewer_count: number;
  platforms: string[];
  cross_platform: boolean;
}

export interface LiveSearchCounts {
  review_count: number;
  fresh_only: boolean;
  agreement_pct: number;
  clusters: LiveSearchClusterOut[];
  pack: ContextPack;
}

// ---------------------------------------------------------------------------
// Works (api/routers/reads.py)
// ---------------------------------------------------------------------------

export interface WorkOut {
  id: string;
  title: string;
  author: string | null;
  agg_rating_avg: number | null;
  agg_rating_count: number | null;
  review_count: number;
}

export interface ClusterOut {
  id: string;
  label: string;
  representative: string;
  member_count: number;
  reviewer_count: number;
  helpful_weight: number;
  platforms: string[];
  cross_platform: boolean;
  work_id: string | null;
  bisac_code: string | null;
}

export interface WorkDetailOut {
  id: string;
  title: string;
  author: string | null;
  agg_rating_avg: number | null;
  agg_rating_count: number | null;
  review_count: number;
  clusters: ClusterOut[];
}

// ---------------------------------------------------------------------------
// Scores / candidates (api/routers/reads.py)
// ---------------------------------------------------------------------------

export type ScoreScope = "work" | "bisac";

export interface ScoreOut {
  scope: ScoreScope;
  ref_id: string;
  gap_score: number;
  demand_score: number;
  supply_scarcity: number;
  unmet_need: number;
  confidence: number;
  sample_size: number;
  platforms_used: string[];
  incomplete: boolean;
  blind_spot: boolean;
  recent_supply_surge: boolean;
}

/** GET /projects/{id}/candidates — a ScoreOut joined to a human title. */
export interface CandidateOut extends ScoreOut {
  title: string;
}

// ---------------------------------------------------------------------------
// Request bodies (api/schemas.py)
// ---------------------------------------------------------------------------

export interface SearchRequestBody {
  title?: string;
  isbn?: string;
}

export interface SeedRequestBody {
  meta_limit: number;
  review_limit: number;
  max_works: number;
}

export interface JobIdResponse {
  job_id: string;
}
