import { MarkdownView } from "@/components/MarkdownView";
import { RoutingLine } from "@/components/RoutingLine";
import { TraceAccordion } from "@/components/TraceAccordion";
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
  const { insertChip, setEvidencePulse, answerFocus, setAnswerFocus } = useConsole();

  if (turn.status === "pending") {
    return <RoutingLine query={query} sar={hasSar} />;
  }

  if (turn.status === "failed") {
    return (
      <div>
        <p className="text-[15px] leading-relaxed text-destructive">{turn.error ?? "The run did not complete."}</p>
      </div>
    );
  }

  const routed =
    turn.trace?.find((t) => t.tool === "router")?.params.specialist ??
    turn.trace?.find((t) => t.tool !== "gate" && t.tool !== "router")?.tool ??
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

      {turn.trace?.length ? (
        <TraceAccordion steps={turn.trace} confidence={turn.confidence} focus={answerFocus} />
      ) : null}

      <div className="mt-5 flex flex-wrap gap-2">
        {followUpQuestions(query).map((chip) => (
          <button key={chip} type="button" onClick={() => insertChip(chip)} className="sq-chip">
            {chip}
          </button>
        ))}
      </div>
    </div>
  );
}
