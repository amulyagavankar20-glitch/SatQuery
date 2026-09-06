import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { formatTraceChain, formatTraceStep } from "@/lib/thinking";
import type { TraceStep } from "@/lib/types";
import { cn } from "@/lib/utils";

export function TraceAccordion({
  steps,
  confidence,
  focus,
}: {
  steps: TraceStep[];
  confidence?: string | null;
  focus?: boolean;
}) {
  return (
    <Accordion type="single" collapsible className="border-hairline mt-2 min-w-0 border-t">
      <AccordionItem value="trace" className="min-w-0 border-0">
        <AccordionTrigger
          id="sq-trace"
          className={cn("min-w-0 font-mono text-[11px] tracking-wide", focus && "text-primary")}
        >
          <span className="min-w-0 truncate">{formatTraceChain(steps, confidence)}</span>
        </AccordionTrigger>
        <AccordionContent>
          <ol className="flex flex-col gap-1.5 font-mono text-[11px] leading-relaxed text-mute">
            {steps.map((step) => (
              <li key={step.tool} className={cn(focus && "text-ink")}>
                {formatTraceStep(step)}
                {step.elapsedMs != null ? <span className="ml-2 text-mute">{step.elapsedMs} ms</span> : null}
              </li>
            ))}
          </ol>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}
