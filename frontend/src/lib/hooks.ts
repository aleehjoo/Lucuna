"use client";

import {
  type Query,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "./api";
import type {
  CandidateOut,
  HealthOut,
  JobIdResponse,
  JobOut,
  ProjectOut,
  SearchRequestBody,
  SeedRequestBody,
  WorkDetailOut,
  WorkOut,
} from "./types";

// ---------------------------------------------------------------------------
// Job polling — the crux of this module. Exported standalone so it can be
// unit-tested without mounting a component (per the task brief, Step 4).
// Stops polling once the job reaches a terminal status (done|error); polls
// every 1.5s otherwise. `enabled: !!jobId` (set by useJob) means a null
// jobId never reaches this function in practice.
// ---------------------------------------------------------------------------
export function jobRefetchInterval(
  query: Query<JobOut, Error, JobOut, readonly [string, string | null]>,
): number | false {
  const status = query.state.data?.status;
  return status === "done" || status === "error" ? false : 1500;
}

// ---------------------------------------------------------------------------
// Health polling — mirrors jobRefetchInterval's shape: exported standalone so
// the stop condition (models warmed up) is unit-testable without mounting a
// component. Polls every 5s until models_ready, then stops.
// ---------------------------------------------------------------------------
export function healthRefetchInterval(
  query: Query<HealthOut, Error, HealthOut, readonly [string]>,
): number | false {
  return query.state.data?.models_ready ? false : 5000;
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"] as const,
    queryFn: () => api.get<HealthOut>("/health"),
    refetchInterval: healthRefetchInterval,
  });
}

export const useProjects = () =>
  useQuery({
    queryKey: ["projects"],
    queryFn: () => api.get<ProjectOut[]>("/projects"),
  });

export const useProject = (id: string | null) =>
  useQuery({
    queryKey: ["project", id],
    enabled: !!id,
    queryFn: () => api.get<ProjectOut>(`/projects/${id}`),
  });

export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: ["job", jobId] as const,
    enabled: !!jobId,
    queryFn: () => api.get<JobOut>(`/jobs/${jobId}`),
    refetchInterval: jobRefetchInterval,
  });
}

export function useStartSearch(projectId: string) {
  return useMutation({
    mutationFn: (body: SearchRequestBody) =>
      api.post<JobIdResponse>(`/projects/${projectId}/search`, body),
  });
}

export function useStartSeed(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SeedRequestBody) =>
      api.post<JobIdResponse>(`/projects/${projectId}/seed`, body),
    onSettled: () => qc.invalidateQueries({ queryKey: ["projects"] }),
  });
}

export function useStartSweep(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<JobIdResponse>(`/projects/${projectId}/sweep`, {}),
    onSettled: () => qc.invalidateQueries({ queryKey: ["candidates", projectId] }),
  });
}

export const useCandidates = (id: string | null) =>
  useQuery({
    queryKey: ["candidates", id],
    enabled: !!id,
    queryFn: () => api.get<CandidateOut[]>(`/projects/${id}/candidates`),
  });

export const useWorks = (id: string | null) =>
  useQuery({
    queryKey: ["works", id],
    enabled: !!id,
    queryFn: () => api.get<WorkOut[]>(`/projects/${id}/works`),
  });

export const useWork = (projectId: string | null, workId: string | null) =>
  useQuery({
    queryKey: ["work", projectId, workId],
    enabled: !!projectId && !!workId,
    queryFn: () => api.get<WorkDetailOut>(`/projects/${projectId}/works/${workId}`),
  });
