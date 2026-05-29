// --- Starter-kit-kept types (file upload + browser + dashboard primitives) ---

export type FileStatus = "uploading" | "complete" | "error";

export interface FileMetadata {
  key: string;
  filename: string;
  folder: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
}

// Fingerprint-only metadata for the kept /upload reference surface.
// The starter kit declared image_*, pdf_*, and media (duration/codec/bitrate)
// fields here; this sample's metadata extractor doesn't populate any of them,
// so they were removed in lockstep with services/api/app/service/metadata.py.
export interface FileMetadataDetail {
  filename: string;
  size_bytes: number;
  size_human: string;
  mime_type: string;
  extension: string;
  md5: string;
  sha256: string;
  uploaded_at: string;
}

export interface FileUploadResponse {
  key: string;
  filename: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
  metadata: FileMetadataDetail | null;
}

export interface DailyUploadCount {
  date: string;
  uploads: number;
}

export interface UploadStats {
  total_files: number;
  total_size_bytes: number;
  total_size_human: string;
  uploads_today: number;
  total_downloads: number;
}

// --- Voice-agent additions ---

export type ToolName =
  | "account_lookup"
  | "order_status"
  | "create_ticket"
  | "escalate";

export interface IceServer {
  urls: string[];
  username?: string;
  credential?: string;
}

export interface RealtimeSessionToken {
  session_id: string;
  client_secret: string;
  model: string;
  expires_at: string;
  ice_servers: IceServer[];
}

export interface TranscriptTurn {
  speaker: "caller" | "agent";
  text: string;
  started_at: string;
  ended_at: string;
}

export interface ToolEvent {
  tool_call_id: string;
  tool: ToolName;
  args: Record<string, unknown>;
  ok: boolean;
  result: Record<string, unknown> | null;
  error: string | null;
  latency_ms: number;
  timestamp: string;
  status: "ok" | "error" | "interrupted";
}

export interface ToolCallRequest {
  call_id: string;
  tool_call_id: string;
  tool_name: ToolName;
  args: Record<string, unknown>;
}

export interface ToolCallResponse {
  tool_call_id: string;
  ok: boolean;
  result: Record<string, unknown> | null;
  error: string | null;
  latency_ms: number;
}

export interface CallManifest {
  call_id: string;
  started_at: string;
  ended_at: string;
  duration_seconds: number;
  tool_count: number;
  deflected: boolean;
  audio_bytes: number;
  model: string;
}

export interface Call {
  call_id: string;
  started_at: string;
  ended_at: string;
  duration_seconds: number;
  tool_count: number;
  deflected: boolean;
  summary_line: string;
  complete: boolean;
}

export interface CallDetail {
  manifest: CallManifest;
  transcript: TranscriptTurn[];
  tools: ToolEvent[];
  summary_markdown: string;
}

export interface CallFinalizeRequest {
  call_id: string;
  started_at: string;
  ended_at: string;
  transcript: TranscriptTurn[];
  tools: ToolEvent[];
  audio_base64: string;
  model: string;
}

export interface DailyCallCount {
  date: string;
  calls: number;
}

export interface CallStats {
  calls_today: number;
  calls_this_week: number;
  avg_duration_seconds: number;
  total_tool_calls: number;
  tickets_created: number;
  deflection_rate: number;
  tool_breakdown: Record<string, number>;
}
