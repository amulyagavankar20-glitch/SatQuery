import { useEffect, useRef, useState, type RefObject } from "react";
import { ChevronDown, ChevronUp, Copy, Send } from "lucide-react";
import { cn } from "@/lib/cn";
import { QUESTION_CHIPS } from "@/lib/chips";
import { copyText, formatClock, formatElapsed } from "@/lib/format";
import { traceTone } from "@/lib/pipeline";
import type { JobView } from "@/lib/schema";

type ChatMessage = {
  id: string;
  role: "user" | "ai" | "system";
  text: string;
  timestamp?: string;
  job?: JobView;
};

function TypingIndicator({ elapsed }: { elapsed: number | null }) {
  return (
    <div className="chat-bubble chat-bubble-ai fade-in">
      <div className="flex items-center gap-3">
        <div className="typing-dots">
          <span />
          <span />
          <span />
        </div>
        <span className="font-mono text-[11px] text-cyan/80">
          Analyzing{elapsed != null ? ` · ${formatElapsed(elapsed)}` : "…"}
        </span>
      </div>
    </div>
  );
}

function TraceRail({ job }: { job: JobView }) {
  const [open, setOpen] = useState(false);
  const traces = job.traces ?? [];
  if (!traces.length) return null;

  return (
    <div className="mt-2 border-t border-white/5 pt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between font-mono text-[10px] text-muted/80 transition hover:text-muted"
      >
        <span>▸ Trace ({traces.length} events)</span>
        {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>
      {open && (
        <ol className="sq-scroll mt-1.5 max-h-[180px] overflow-y-auto space-y-1 pr-1">
          {traces.map((trace, i) => {
            const tone = traceTone(trace.event_type);
            return (
              <li
                key={`${trace.timestamp}-${i}`}
                className="flex items-start gap-2 rounded-md px-1.5 py-1 transition hover:bg-white/[0.03]"
              >
                <span
                  className={cn(
                    "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
                    tone === "ok" && "bg-ok",
                    tone === "bad" && "bg-bad",
                    tone === "warn" && "bg-gold",
                    tone === "cyan" && "bg-cyan",
                    tone === "muted" && "bg-muted/50",
                  )}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-[11px] text-ink/80">{trace.node_name ?? trace.event_type}</span>
                    <span className="font-mono text-[9px] text-muted/60">{formatClock(trace.timestamp)}</span>
                  </div>
                  <div className="font-mono text-[9px] text-muted/70">
                    {trace.event_type}
                    {trace.tool_id ? ` · ${trace.tool_id}` : ""}
                  </div>
                  {trace.message && (
                    <div className="mt-0.5 text-[10px] text-ink/50">{trace.message}</div>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}

function AIResponseBubble({
  job,
  onLightbox,
  apiUrl,
}: {
  job: JobView;
  onLightbox: (src: string) => void;
  apiUrl: (path: string) => string;
}) {
  const answer = job.answer;
  const tools =
    job.route && Array.isArray((job.route as { tools?: string[] }).tools)
      ? ((job.route as { tools?: string[] }).tools ?? [])
      : [];

  const confidenceClass = (value: string | null | undefined) => {
    const v = (value ?? "").toUpperCase();
    if (v === "HIGH") return "text-ok";
    if (v === "LOW") return "text-bad";
    if (v === "MEDIUM") return "text-gold";
    return "text-muted";
  };

  const previewSrc = job.assets[0]?.preview_url
    ? (job.status === "completed" || job.tile_count > 0) ? apiUrl(job.assets[0].preview_url) : null
    : null;

  return (
    <div className="chat-bubble chat-bubble-ai slide-up">
      {/* Meta badges */}
      <div className="mb-2 flex flex-wrap items-center gap-1.5">
        <span className="rounded-md bg-white/5 px-1.5 py-0.5 font-mono text-[9px] text-muted/80">
          {job.task ?? "UNROUTED"}
        </span>
        {job.input_class && (
          <span className="rounded-md bg-white/5 px-1.5 py-0.5 font-mono text-[9px] text-muted/80">
            {job.input_class}
          </span>
        )}
        {answer?.confidence && (
          <span className={cn("rounded-md bg-white/5 px-1.5 py-0.5 font-mono text-[9px]", confidenceClass(answer.confidence))}>
            {answer.confidence}
          </span>
        )}
        {tools.length > 0 && (
          <span className="rounded-md bg-cyan/8 px-1.5 py-0.5 font-mono text-[9px] text-cyan/80">
            {tools.join(" → ")}
          </span>
        )}
      </div>

      {/* Answer text */}
      <p className="text-[13px] leading-relaxed text-ink/90">
        {answer?.text ??
          (job.refusal_reason
            ? job.refusal_reason
            : "Processing...")}
      </p>

      {/* Model info */}
      {answer && (
        <p className="mt-2 font-mono text-[9px] text-muted/60">
          {answer.model}
          {answer.backend === "mock" ? (
            <span className="ml-1.5 text-gold/70">mock · InternVL not loaded</span>
          ) : (
            ` · ${answer.backend}`
          )}
        </p>
      )}

      {/* Composite preview */}
      {previewSrc && (
        <button type="button" className="mt-2.5 block w-full" onClick={() => onLightbox(previewSrc)}>
          <img
            src={previewSrc}
            alt="Processed composite"
            className="max-h-28 w-full rounded-lg border border-white/8 bg-black/30 object-contain transition duration-300 hover:border-saffron/30"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.display = "none";
            }}
          />
        </button>
      )}

      {/* Tile strip */}
      {job.tile_count > 0 && (
        <div className="sq-scroll mt-2 flex gap-1.5 overflow-x-auto pb-1">
          {Array.from({ length: Math.min(job.tile_count, 12) }, (_, i) => {
            const src = apiUrl(`/jobs/${job.job_id}/artifacts/tiles/${i}`);
            return (
              <button
                key={i}
                type="button"
                onClick={() => onLightbox(src)}
                className="h-12 w-12 shrink-0 overflow-hidden rounded-md border border-white/8 bg-black/30 transition hover:border-saffron/40"
              >
                <img src={src} alt={`Tile ${i}`} className="h-full w-full object-cover" />
              </button>
            );
          })}
        </div>
      )}

      {/* Copy answer */}
      {answer?.text && (
        <button
          type="button"
          onClick={() => void copyText(answer.text!)}
          className="mt-2 flex items-center gap-1 font-mono text-[9px] text-muted/60 transition hover:text-saffron"
        >
          <Copy className="h-3 w-3" /> Copy answer
        </button>
      )}

      {/* Expandable trace */}
      <TraceRail job={job} />
    </div>
  );
}

export function ChatPanel({
  query,
  job,
  running,
  canRun,
  elapsedMs,
  queryRef,
  onQueryChange,
  onRun,
  onLightbox,
  apiUrl,
  runError,
}: {
  query: string;
  job: JobView | null;
  running: boolean;
  canRun: boolean;
  elapsedMs: number | null;
  queryRef: RefObject<HTMLTextAreaElement | null>;
  onQueryChange: (q: string) => void;
  onRun: () => void;
  onLightbox: (src: string) => void;
  apiUrl: (path: string) => string;
  runError: string | null;
}) {
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Build message list from current job state
  const messages: ChatMessage[] = [];

  if (job?.query) {
    messages.push({
      id: "user-query",
      role: "user",
      text: job.query,
    });
  }

  if (job && (job.status === "completed" || job.status === "failed" || job.status === "refused")) {
    messages.push({
      id: "ai-response",
      role: "ai",
      text: job.answer?.text ?? job.refusal_reason ?? "No response",
      job,
    });
  }

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages.length, running]);

  return (
    <section className="glass rise flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl" style={{ animationDelay: "80ms" }}>
      {/* Header */}
      <header className="flex items-center justify-between border-b border-white/8 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-cyan/60" />
          <span className="font-mono text-[11px] font-medium tracking-[0.2em] text-ink/90 uppercase">
            Query
          </span>
        </div>
        <span className="font-mono text-[10px] text-muted/70">
          {job?.status ?? "idle"}
        </span>
      </header>

      {/* Messages area */}
      <div className="sq-scroll flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-3.5">
        {/* Empty state */}
        {messages.length === 0 && !running && (
          <div className="flex flex-1 flex-col items-center justify-center text-center">
            <p className="text-[13px] text-muted/70">Ask about your satellite scene</p>
            <p className="mt-1 font-mono text-[10px] text-muted/50">
              Select a chip below or type your question
            </p>
          </div>
        )}

        {/* User message */}
        {messages.filter((m) => m.role === "user").map((msg) => (
          <div key={msg.id} className="chat-bubble chat-bubble-user slide-up">
            <p className="text-[13px] text-ink/90">{msg.text}</p>
          </div>
        ))}

        {/* Typing indicator while running */}
        {running && <TypingIndicator elapsed={elapsedMs} />}

        {/* AI response */}
        {messages.filter((m) => m.role === "ai").map((msg) => (
          msg.job ? (
            <AIResponseBubble
              key={msg.id}
              job={msg.job}
              onLightbox={onLightbox}
              apiUrl={apiUrl}
            />
          ) : null
        ))}

        <div ref={messagesEndRef} />
      </div>

      {/* Chip suggestions */}
      <div className="flex flex-wrap gap-1.5 border-t border-white/5 px-3.5 pt-2.5 pb-1">
        {QUESTION_CHIPS.map((chip, i) => (
          <button
            key={chip.id}
            type="button"
            onClick={() => onQueryChange(chip.query)}
            title={`${i + 1} · ${chip.query}`}
            className={cn(
              "rounded-full border px-2 py-0.5 font-mono text-[9px] tracking-[0.12em] uppercase transition duration-200 active:scale-95",
              query === chip.query
                ? "border-saffron/60 bg-saffron/12 text-saffron"
                : "border-white/8 text-muted/70 hover:border-cyan/30 hover:text-ink",
            )}
          >
            <span className="mr-1 text-muted/50">{i + 1}</span>
            {chip.label}
          </button>
        ))}
      </div>

      {/* Input area */}
      <div className="border-t border-white/8 p-3">
        <div className="flex items-end gap-2">
          <textarea
            ref={queryRef}
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                e.preventDefault();
                if (canRun && !running) onRun();
              }
            }}
            rows={1}
            placeholder="Ask about your scene…"
            className="min-h-[36px] max-h-[120px] w-full resize-none rounded-lg border border-white/8 bg-black/20 px-3 py-2 text-[13px] leading-relaxed text-ink outline-none transition focus:border-cyan/40"
            style={{
              height: "auto",
              overflow: "hidden",
            }}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement;
              target.style.height = "auto";
              target.style.height = `${Math.min(target.scrollHeight, 120)}px`;
            }}
          />
          <button
            type="button"
            disabled={!canRun || running}
            onClick={onRun}
            className={cn(
              "grid h-9 w-9 shrink-0 place-items-center rounded-lg border transition",
              canRun && !running
                ? "border-cyan/40 bg-cyan/10 text-cyan hover:bg-cyan/20"
                : "border-white/8 text-muted/40",
              running && "animate-[pulse-glow_1.8s_ease-in-out_infinite]",
            )}
            title="Run analysis (⌘/Ctrl Enter)"
          >
            <Send className="h-3.5 w-3.5" />
          </button>
        </div>
        {runError && (
          <p className="mt-1.5 font-mono text-[10px] text-bad">{runError}</p>
        )}
        <p className="mt-1.5 font-mono text-[9px] text-muted/50">
          ⌘/Ctrl Enter to run · 1–5 for chips
        </p>
      </div>
    </section>
  );
}
