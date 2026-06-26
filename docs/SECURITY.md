<!-- last_verified: 2026-05-28 -->
# Security

Security principles and implementation for the gpt-realtime-2-customer-support-voice-agent sample.

## Trust Boundaries

- **Frontend -> API**: CORS-restricted to configured origins, scoped to `GET/POST/DELETE/OPTIONS`
- **API -> B2**: Authenticated via `B2_APPLICATION_KEY_ID` + `B2_APPLICATION_KEY`, signature v4, S3 endpoint derived from `B2_REGION`
- **API -> OpenAI**: Authenticated via `OPENAI_API_KEY`. The key never leaves the API process.
- **Client -> OpenAI Realtime**: Direct WebRTC peer connection authenticated by an **ephemeral session token** minted by the API (`POST /realtime/session`). The token is short-lived (≤ 1 minute by default) and scoped to a single Realtime session. The API never proxies audio bytes.
- **Client -> B2**: Presigned URLs for audio playback (10-min expiry, `Content-Disposition: inline`)

## OpenAI Key Handling

- `OPENAI_API_KEY` lives only in the server environment (`.env`, never `NEXT_PUBLIC_*`).
- The browser receives only an ephemeral session token, which OpenAI rotates per-session.
- If the session token leaks, the blast radius is one Realtime session, not the underlying API key.

## Audio Data Residency

- All call audio, transcripts, and tool traces persist to the Backblaze B2 bucket configured by `B2_BUCKET_NAME`.
- No third-party CDN or transcription cache is involved beyond OpenAI's Realtime API itself.
- Deleting a call (`DELETE /calls/{id}`) removes every object under the `calls/<id>/` prefix.

## Upload Validation (reference upload route)

The starter-kit upload surface is kept for operator-facing reference uploads (e.g. seeding documentation into the bucket). All starter-kit defenses still apply:

- Filename sanitization: path traversal, null bytes, unsafe chars stripped
- MIME/extension consistency check against allowlist
- Chunked streaming with size enforcement (100MB default)
- Content-type allowlist (images, PDFs, text, archives, audio/video)
- Empty file rejection

## File Key Validation

- Empty keys rejected
- Path traversal patterns rejected (`../`, `%2e%2e`, backslashes, null bytes)
- The bucket is the only access boundary — add prefix scoping in
  `services/api/app/service/files.py::validate_key` if your deployment
  shares a bucket with other workloads

## Download / Playback Safety

- Audio presigned URLs use `response-content-disposition=inline` so the browser audio element can stream directly
- Document download presigned URLs (`/files/{key}/download`) force `Content-Disposition: attachment`

## Secrets Management

- All secrets loaded via environment variables (pydantic-settings)
- Never committed to source control
- `.env.example` documents required variables without values

## Agent Security Rules

- Never commit `.env`, credentials, or API keys
- Never weaken validation without explicit instruction
- Never bypass CORS, auth, or input sanitization
- Always validate at system boundaries
- Never expose `OPENAI_API_KEY` to the browser — only ephemeral session tokens
