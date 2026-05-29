import { CallConsole } from "@/components/call/CallConsole";

export default function CallPage() {
  return (
    <div className="space-y-6">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">Call</h1>
        <p className="text-sm text-muted-foreground mt-1.5">
          Live voice conversation with the support agent. Audio is captured in your
          browser and streamed directly to OpenAI; tool calls run on our backend.
        </p>
      </div>
      <CallConsole />
    </div>
  );
}
