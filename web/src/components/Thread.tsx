import { useEffect, useRef } from "react";

import { AssistantTurn } from "@/components/AssistantTurn";
import { EmptyState } from "@/components/EmptyState";
import { useConsole } from "@/state/console";

export function Thread() {
  const { turns, hasScene, layers, setLayer, hasSar, slots } = useConsole();
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [turns]);

  if (!hasScene && turns.length === 0) {
    return (
      <div ref={scrollerRef} className="sq-scroll min-h-0 flex-1 overflow-y-auto">
        <EmptyState />
      </div>
    );
  }

  return (
    <div ref={scrollerRef} className="sq-scroll min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-8 px-6 py-8 pb-24">
        {turns.length === 0 ? (
          <div className="flex min-h-[calc(100%-1rem)] flex-col items-center justify-center py-16 text-center">
            <div className="flex gap-2">
              {slots
                .filter((s) => s.previewUrl)
                .map((s) => (
                  <img
                    key={s.id}
                    src={s.previewUrl}
                    alt={s.filename}
                    className="h-20 w-28 rounded-lg border border-hairline object-cover"
                  />
                ))}
            </div>
            <p className="mt-6 text-[16px] text-ink">Ask this scene.</p>
            <p className="mt-2 text-[13px] text-mute">1–5 inserts an official question. Ctrl+Enter sends.</p>
          </div>
        ) : (
          turns.map((turn, index) => {
            const previous = turns[index - 1];
            if (turn.role === "user") {
              return (
                <div key={turn.id} className="sq-enter flex justify-end">
                  <div className="max-w-[36rem] rounded-xl bg-raised px-4 py-3 text-[15px] leading-relaxed text-ink">
                    {turn.query}
                  </div>
                </div>
              );
            }
            return (
              <div key={turn.id} className="sq-enter">
                <AssistantTurn
                  turn={turn}
                  query={previous?.role === "user" ? previous.query : ""}
                  layers={layers}
                  onLayer={setLayer}
                  hasSar={hasSar}
                />
              </div>
            );
          })
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
