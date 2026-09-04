import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import type { TraceStep } from "@/lib/types";

export function TraceAccordion({ steps }: { steps: TraceStep[] }) {
  return (
    <Accordion type="single" collapsible className="border-hairline mt-2 border-t">
      <AccordionItem value="trace" className="border-0">
        <AccordionTrigger>Trace</AccordionTrigger>
        <AccordionContent>
          <ol className="flex flex-col gap-4">
            {steps.map((step) => (
              <li key={step.tool}>
                <div className="flex items-baseline gap-3">
                  <span className="font-mono text-[12px] text-ink">{step.tool}</span>
                  {step.elapsedMs != null ? (
                    <span className="font-mono text-[11px] text-mute">{step.elapsedMs} ms</span>
                  ) : null}
                </div>
                <pre className="font-mono mt-1.5 overflow-x-auto text-[11px] leading-relaxed text-mute">
                  {JSON.stringify(step.params, null, 2)}
                </pre>
              </li>
            ))}
          </ol>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}
