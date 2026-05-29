"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  deleteCall,
  deleteFile,
  getCall,
  getCallActivity,
  getCallAudioUrl,
  getCallStats,
  getCalls,
  getFiles,
  getFileStats,
  getPreviewUrl,
  getUploadActivity,
} from "@/lib/api-client";
import type {
  Call,
  CallDetail,
  CallStats,
  DailyCallCount,
  FileMetadata,
} from "@gpt-realtime-2-customer-support-voice-agent/shared";

// Single source of truth for query keys.
export const qk = {
  all: ["b2"] as const,
  // Files (starter-kit-kept)
  files: (prefix?: string, limit?: number) =>
    [...qk.all, "files", prefix ?? "", limit ?? 100] as const,
  fileStats: () => [...qk.all, "files", "stats"] as const,
  uploadActivity: (days: number) =>
    [...qk.all, "files", "stats", "activity", days] as const,
  preview: (key: string) => [...qk.all, "preview", key] as const,
  // Calls (this sample)
  calls: (limit?: number) => [...qk.all, "calls", limit ?? 100] as const,
  callStats: () => [...qk.all, "calls", "stats"] as const,
  callActivity: (days: number) =>
    [...qk.all, "calls", "stats", "activity", days] as const,
  callDetail: (id: string) => [...qk.all, "calls", "detail", id] as const,
  callAudio: (id: string) => [...qk.all, "calls", "audio", id] as const,
};

// --- Files (kept) ---

export function useFiles(prefix = "", limit = 100) {
  return useQuery<FileMetadata[], ApiError>({
    queryKey: qk.files(prefix, limit),
    queryFn: () => getFiles(prefix, limit),
  });
}

export function useFileStats() {
  return useQuery({ queryKey: qk.fileStats(), queryFn: getFileStats });
}

export function useUploadActivity(days = 7) {
  return useQuery({
    queryKey: qk.uploadActivity(days),
    queryFn: () => getUploadActivity(days),
  });
}

export function usePreviewUrl(key: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: qk.preview(key ?? ""),
    queryFn: () => getPreviewUrl(key as string),
    enabled: enabled && !!key,
    staleTime: 60_000,
  });
}

export function useDeleteFile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (fileKey: string) => deleteFile(fileKey),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.all });
    },
  });
}

// --- Calls (this sample) ---

export function useCalls(limit = 100) {
  return useQuery<Call[], ApiError>({
    queryKey: qk.calls(limit),
    queryFn: () => getCalls(limit),
  });
}

export function useCallStats() {
  return useQuery<CallStats, ApiError>({
    queryKey: qk.callStats(),
    queryFn: getCallStats,
  });
}

export function useCallActivity(days = 7) {
  return useQuery<DailyCallCount[], ApiError>({
    queryKey: qk.callActivity(days),
    queryFn: () => getCallActivity(days),
  });
}

export function useCallDetail(callId: string | undefined, enabled: boolean) {
  return useQuery<CallDetail, ApiError>({
    queryKey: qk.callDetail(callId ?? ""),
    queryFn: () => getCall(callId as string),
    enabled: enabled && !!callId,
  });
}

export function useCallAudioUrl(callId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: qk.callAudio(callId ?? ""),
    queryFn: () => getCallAudioUrl(callId as string),
    enabled: enabled && !!callId,
    staleTime: 60_000,
  });
}

export function useDeleteCall() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (callId: string) => deleteCall(callId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.all });
    },
  });
}
