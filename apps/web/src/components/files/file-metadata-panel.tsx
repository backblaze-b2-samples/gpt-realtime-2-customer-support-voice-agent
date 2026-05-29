"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { FileMetadataDetail } from "@gpt-realtime-2-customer-support-voice-agent/shared";

interface FileMetadataPanelProps {
  metadata: FileMetadataDetail;
}

function MetaRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono text-right max-w-[60%] truncate">{value}</span>
    </div>
  );
}

// This sample's metadata extractor (services/api/app/service/metadata.py) only
// computes fingerprint info — size, MIME, extension, MD5, SHA-256. The image /
// PDF / media branches that shipped with the starter kit were removed when
// metadata.py was trimmed; they used to render here but always had null inputs.
export function FileMetadataPanel({ metadata }: FileMetadataPanelProps) {
  return (
    <Card>
      <CardHeader className="pb-3 px-5 pt-5">
        <CardTitle className="card-title">File Details</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 px-5 pb-5">
        <MetaRow label="Filename" value={metadata.filename} />
        <MetaRow label="Size" value={metadata.size_human} />
        <MetaRow label="Type" value={metadata.mime_type} />
        <MetaRow label="Extension" value={metadata.extension || "none"} />

        <Separator />
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Checksums
        </p>
        <MetaRow label="MD5" value={metadata.md5} />
        <MetaRow label="SHA-256" value={metadata.sha256} />

        <Separator />
        <MetaRow
          label="Uploaded"
          value={new Date(metadata.uploaded_at).toLocaleString()}
        />
      </CardContent>
    </Card>
  );
}
