/**
 * Pure helpers for interpreting OpenAI Realtime data-channel events.
 *
 * Kept out of `use-realtime-call.ts` so the React hook stays focused on
 * lifecycle (peer connection, recorder, state) and stays under the
 * structural-test 300-line ceiling. These helpers hold no React state
 * — callers pass in setters and the dispatch handle for tool replies.
 */

import { invokeTool } from "@/lib/api-client";
import type {
  ToolEvent,
  ToolName,
  TranscriptTurn,
} from "@gpt-realtime-2-customer-support-voice-agent/shared";

/** A loosely-typed Realtime event from the data channel. */
type RealtimeEvent = { type?: string; [key: string]: unknown };

/** Side-effects the event handler may need to perform on the hook. */
export interface RealtimeEventDispatch {
  /** Append a tool event to the in-memory trace. */
  appendTool: (event: ToolEvent) => void;
  /** Append a transcript turn (caller or agent). */
  appendTurn: (turn: TranscriptTurn) => void;
  /** Surface an error to the UI (e.g. tool-dispatch failure). */
  setError: (msg: string) => void;
  /** Send raw JSON down the data channel. */
  sendDataChannel: (payload: unknown) => void;
}

/**
 * Process a single Realtime data-channel event.
 *
 * Recognizes:
 *  - `response.function_call_arguments.done` — model issued a tool call
 *  - `response.audio_transcript.done`         — agent transcript turn
 *  - `conversation.item.input_audio_transcription.completed` — caller turn
 *
 * Anything else is silently ignored (we only care about the events that
 * actually shape the per-call bundle on B2).
 */
export async function handleRealtimeEvent(
  raw: MessageEvent,
  callId: string | null,
  dispatch: RealtimeEventDispatch,
): Promise<void> {
  let event: RealtimeEvent;
  try {
    event = JSON.parse(raw.data);
  } catch {
    return;
  }

  if (isFunctionCallArgumentsDone(event)) {
    await handleToolCall(event, callId, dispatch);
    return;
  }

  if (
    event.type === "response.audio_transcript.done" &&
    typeof event.transcript === "string"
  ) {
    dispatch.appendTurn(makeTurn("agent", event.transcript));
    return;
  }

  if (
    event.type === "conversation.item.input_audio_transcription.completed" &&
    typeof event.transcript === "string"
  ) {
    dispatch.appendTurn(makeTurn("caller", event.transcript));
  }
}

function isFunctionCallArgumentsDone(event: RealtimeEvent): boolean {
  return (
    event.type === "response.function_call_arguments.done" &&
    typeof event.name === "string" &&
    typeof event.call_id === "string" &&
    typeof event.arguments === "string"
  );
}

async function handleToolCall(
  event: RealtimeEvent,
  callId: string | null,
  dispatch: RealtimeEventDispatch,
): Promise<void> {
  if (!callId) return;
  const toolName = event.name as ToolName;
  const toolCallId = event.call_id as string;
  const args = safeParseJson(event.arguments as string);

  try {
    const response = await invokeTool({
      call_id: callId,
      tool_call_id: toolCallId,
      tool_name: toolName,
      args,
    });
    // Replay the tool result into the data channel so the model can
    // resume speaking. Two messages: the function-output item, then a
    // response.create to trigger continuation.
    dispatch.sendDataChannel({
      type: "conversation.item.create",
      item: {
        type: "function_call_output",
        call_id: toolCallId,
        output: JSON.stringify(response.result ?? { error: response.error }),
      },
    });
    dispatch.sendDataChannel({ type: "response.create" });
    dispatch.appendTool({
      tool_call_id: response.tool_call_id,
      tool: toolName,
      args,
      ok: response.ok,
      result: response.result,
      error: response.error,
      latency_ms: response.latency_ms,
      timestamp: new Date().toISOString(),
      status: response.ok ? "ok" : "error",
    });
  } catch (err) {
    dispatch.setError(
      err instanceof Error ? err.message : "Tool dispatch failed",
    );
  }
}

function safeParseJson(raw: string): Record<string, unknown> {
  try {
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function makeTurn(speaker: "caller" | "agent", text: string): TranscriptTurn {
  const now = new Date().toISOString();
  return { speaker, text, started_at: now, ended_at: now };
}
