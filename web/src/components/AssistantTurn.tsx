import { LulcPanel } from "@/components/LulcPanel";
import { MarkdownView } from "@/components/MarkdownView";
import { RoutingLine } from "@/components/RoutingLine";
import { TraceAccordion } from "@/components/TraceAccordion";
import { apiUrl } from "@/lib/api";
import { followUpQuestions, specialistId } from "@/lib/thinking";
import type { AssistantTurn as AssistantTurnModel } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useConsole } from "@/state/console";

export function AssistantTurn({
  turn,
  query,
  hasSar,
}: {
  turn: AssistantTurnModel;
  query: string;
  hasSar: boolean;
}) {
  const { insertChip, setEvidencePulse, answerFocus, setAnswerFocus, slots, activeSlot } = useConsole();

  if (turn.status === "pending") {
    return <RoutingLine query={query} sar={hasSar} />;
  }

  const isModalityMismatch =
    (turn.error && turn.error.includes("Selected asset is")) ||
    (turn.answer && turn.answer.includes("Selected asset is")) ||
    (turn.error && turn.error.toLowerCase().includes("modality mismatch")) ||
    (turn.answer && turn.answer.toLowerCase().includes("modality mismatch"));

  if (turn.status === "failed") {
    const qLower = query.toLowerCase();
    const asksSar = qLower.includes("sar") || qLower.includes("radar") || qLower.includes("sentinel-1");
    const reqMod = asksSar ? "SAR" : "OPTICAL";
    const availMod = asksSar ? "OPTICAL" : "SAR";
    const msg = turn.error || turn.answer || "The run could not proceed due to input or modality incompatibility.";

    return (
      <div className="space-y-4">
        {isModalityMismatch ? (
          <div className="rounded-xl border border-red-500/30 bg-red-950/20 p-4 text-ink shadow-sm">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-red-400">
              <span className="inline-block h-2 w-2 rounded-full bg-red-500 animate-pulse" />
              Modality Incompatibility
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2 rounded-lg bg-black/40 p-3 font-mono text-xs border border-white/5">
              <div>
                <span className="text-mute block text-[10px] uppercase">Requested Modality</span>
                <span className="text-amber-300 font-semibold">{reqMod}</span>
              </div>
              <div>
                <span className="text-mute block text-[10px] uppercase">Available Modality</span>
                <span className="text-blue-300 font-semibold">{availMod}</span>
              </div>
              <div>
                <span className="text-mute block text-[10px] uppercase">Status</span>
                <span className="text-red-400 font-semibold uppercase">Incompatible</span>
              </div>
            </div>
            <p className="mt-3 text-[14px] leading-relaxed text-red-200">
              {msg}
            </p>
          </div>
        ) : (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3">
            <p className="text-[14px] leading-relaxed text-destructive">{msg}</p>
          </div>
        )}

        {turn.trace?.length ? (
          <TraceAccordion steps={turn.trace} confidence={turn.confidence} focus={answerFocus} />
        ) : null}
      </div>
    );
  }

  const ACTIVE_SPECIALISTS = new Set([
    "sar_map",
    "lulc_map",
    "bit_cd",
    "fusion_s1s2",
    "agreement",
    "coregister",
    "vectorize",
    "align",
  ]);

  const routed =
    turn.trace?.find((t) => ACTIVE_SPECIALISTS.has(t.tool))?.tool ??
    (turn.trace?.find((t) => t.tool === "router")?.params.specialist as string | undefined) ??
    specialistId(query, hasSar);
  const specialist = typeof routed === "string" ? routed : specialistId(query, hasSar);

  return (
    <div>
      <p className="font-mono text-[11px] tracking-wide text-mute">specialist: {specialist}</p>
      {turn.answer ? (
        <div
          id="sq-answer"
          className={cn(
            "mt-3 max-w-3xl rounded-lg p-3 text-ink transition-all",
            answerFocus
              ? "bg-primary/5 ring-1 ring-primary/50"
              : "bg-surface/30 border border-white/5",
          )}
          onMouseEnter={() => setEvidencePulse(true)}
          onMouseLeave={() => {
            setEvidencePulse(false);
            setAnswerFocus(false);
          }}
        >
          <MarkdownView content={turn.answer} />
        </div>
      ) : null}

      {turn.lulc ? <LulcPanel report={turn.lulc} /> : null}

      {turn.trace?.length ? (
        <TraceAccordion steps={turn.trace} confidence={turn.confidence} focus={answerFocus} />
      ) : null}

      <div className="mt-5 flex flex-wrap gap-2">
        <a 
          href={apiUrl(`/jobs/${turn.jobId}/report.pdf`)}
          target="_blank"
          rel="noreferrer"
          className="sq-chip font-semibold !border-primary/50 !bg-primary/10 !text-primary hover:!bg-primary/20"
        >
          📄 Generate Report (PDF)
        </a>
        
        {followUpQuestions(query, slots, activeSlot).map((chip) => (
          <button key={chip} type="button" onClick={() => insertChip(chip)} className="sq-chip">
            {chip}
          </button>
        ))}
      </div>
    </div>
  );
}
