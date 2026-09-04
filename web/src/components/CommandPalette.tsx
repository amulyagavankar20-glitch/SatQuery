import { useNavigate } from "@tanstack/react-router";
import {
  Aperture,
  Braces,
  CircleDashed,
  Command,
  Copy,
  CornerDownLeft,
  FileText,
  Focus,
  FolderOpen,
  GitCompare,
  History,
  Keyboard,
  Layers,
  Map,
  MessageSquare,
  Radio,
  RotateCcw,
  Send,
  Upload,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Kbd } from "@/components/Kbd";
import { DEMOS } from "@/lib/demos";
import { fitLatestMap } from "@/lib/map-registry";
import { cn } from "@/lib/utils";
import { useModLabel } from "@/hooks/use-mod-label";
import { useConsole } from "@/state/console";

type Item = {
  id: string;
  group: string;
  label: string;
  hint?: string;
  kbd?: string;
  thumb?: string;
  icon: ReactNode;
  disabled?: boolean;
  run: () => void;
};

function Highlight({ text, q }: { text: string; q: string }) {
  const needle = q.trim();
  if (!needle) return text;
  const i = text.toLowerCase().indexOf(needle.toLowerCase());
  if (i < 0) return text;
  return (
    <>
      {text.slice(0, i)}
      <span className="text-primary">{text.slice(i, i + needle.length)}</span>
      {text.slice(i + needle.length)}
    </>
  );
}

export function CommandPalette() {
  const nav = useNavigate();
  const ctx = useConsole();
  const mod = useModLabel();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);

  const items = useMemo<Item[]>(() => {
    const q = query.trim();
    const list: Item[] = [];

    if (q.length > 2 && ctx.hasScene) {
      list.push({
        id: "ask",
        group: "Ask",
        label: q,
        hint: "Send this question",
        kbd: "↵",
        icon: <MessageSquare className="size-3.5" />,
        disabled: ctx.sending,
        run: () => ctx.send(q),
      });
    }

    list.push(
      {
        id: "attach",
        group: "Scene",
        label: "Attach GeoTIFF",
        kbd: `${mod}-O`,
        icon: <Upload className="size-3.5" />,
        run: ctx.openFilePicker,
      },
      {
        id: "send",
        group: "Scene",
        label: "Send composer",
        kbd: `${mod}+↵`,
        icon: <Send className="size-3.5" />,
        disabled: !ctx.hasScene || !ctx.draft.trim() || ctx.sending,
        run: () => ctx.send(),
      },
      {
        id: "fit",
        group: "Scene",
        label: "Fit scene",
        kbd: "F",
        icon: <Focus className="size-3.5" />,
        disabled: !ctx.latestJobId,
        run: () => fitLatestMap(),
      },
      {
        id: "clear",
        group: "Scene",
        label: "Clear thread",
        icon: <RotateCcw className="size-3.5" />,
        disabled: ctx.turns.length === 0,
        run: ctx.clearThread,
      },
      {
        id: "reset",
        group: "Scene",
        label: "Reset scene",
        icon: <FolderOpen className="size-3.5" />,
        disabled: !ctx.hasScene,
        run: ctx.resetScene,
      },
      ...DEMOS.map((demo) => ({
        id: `demo-${demo.id}`,
        group: "Demos",
        label: demo.title,
        hint: demo.place,
        thumb: demo.thumb,
        icon: <Layers className="size-3.5" />,
        run: () => {
          ctx.loadDemo(demo.id);
          void nav({ to: "/" });
        },
      })),
      ...ctx.jobs.slice(0, 5).map((job) => ({
        id: `job-${job.id}`,
        group: "Recent",
        label: job.query,
        hint: job.summary,
        icon: <History className="size-3.5" />,
        run: () => {
          ctx.restoreJob(job.id);
          void nav({ to: "/" });
        },
      })),
      {
        id: "opt",
        group: "Layers",
        label: ctx.layers.optical ? "Hide optical" : "Show optical",
        kbd: "O",
        icon: <Aperture className="size-3.5" />,
        run: () => ctx.toggleLayer("optical"),
      },
      {
        id: "sar",
        group: "Layers",
        label: ctx.layers.sar ? "Hide SAR" : "Show SAR",
        kbd: "S",
        icon: <Radio className="size-3.5" />,
        disabled: !ctx.hasSar,
        run: () => ctx.toggleLayer("sar"),
      },
      {
        id: "chg",
        group: "Layers",
        label: ctx.layers.change ? "Hide change" : "Show change",
        kbd: "G",
        icon: <GitCompare className="size-3.5" />,
        run: () => ctx.toggleLayer("change"),
      },
      {
        id: "unc",
        group: "Layers",
        label: ctx.layers.uncertain ? "Hide uncertain" : "Show uncertain",
        kbd: "U",
        icon: <CircleDashed className="size-3.5" />,
        run: () => ctx.toggleLayer("uncertain"),
      },
      {
        id: "copy-job",
        group: "Export",
        label: "Copy job id",
        kbd: "J",
        icon: <Copy className="size-3.5" />,
        disabled: !ctx.latestJobId,
        run: ctx.copyJobId,
      },
      {
        id: "copy-answer",
        group: "Export",
        label: "Copy answer",
        icon: <Copy className="size-3.5" />,
        disabled: !ctx.latestAnswer,
        run: ctx.copyAnswer,
      },
      {
        id: "inspect",
        group: "Export",
        label: "Inspect JSON",
        kbd: "I",
        icon: <Braces className="size-3.5" />,
        disabled: !ctx.inspectJson,
        run: () => ctx.setInspectOpen(true),
      },
      {
        id: "explore",
        group: "Navigate",
        label: "Explore scenes",
        icon: <Map className="size-3.5" />,
        run: () => void nav({ to: "/explore" }),
      },
      {
        id: "jobs",
        group: "Navigate",
        label: "Open jobs",
        icon: <History className="size-3.5" />,
        run: ctx.openJobs,
      },
      {
        id: "about",
        group: "Navigate",
        label: "About",
        icon: <FileText className="size-3.5" />,
        run: () => void nav({ to: "/about" }),
      },
      {
        id: "help",
        group: "Navigate",
        label: "Shortcuts",
        kbd: "?",
        icon: <Keyboard className="size-3.5" />,
        run: () => ctx.setHelpOpen(true),
      },
    );
    return list;
  }, [ctx, nav, mod, query]);

  const filtered = items.filter((item) => {
    if (item.id === "ask") return true;
    const hay = `${item.label} ${item.hint ?? ""} ${item.group}`.toLowerCase();
    return hay.includes(query.toLowerCase().trim());
  });

  useEffect(() => {
    setActive(0);
  }, [query, ctx.paletteOpen]);

  useEffect(() => {
    if (ctx.paletteOpen) {
      setQuery("");
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [ctx.paletteOpen]);

  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>(`[data-pal="${active}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const run = (item: Item) => {
    if (item.disabled) return;
    ctx.setPaletteOpen(false);
    item.run();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(filtered.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(0, i - 1));
    } else if (e.key === "Home") {
      e.preventDefault();
      setActive(0);
    } else if (e.key === "End") {
      e.preventDefault();
      setActive(Math.max(0, filtered.length - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const item = filtered[active];
      if (item) run(item);
    }
  };

  const groups = [...new Set(filtered.map((i) => i.group))];

  return (
    <Dialog open={ctx.paletteOpen} onOpenChange={ctx.setPaletteOpen}>
      <DialogContent
        hideClose
        onOpenAutoFocus={(e) => {
          e.preventDefault();
          requestAnimationFrame(() => inputRef.current?.focus());
        }}
        className="sq-palette top-[14%] left-1/2 w-[min(540px,calc(100%-2rem))] -translate-x-1/2 translate-y-0 gap-0 overflow-hidden bg-[#1A1E22] p-0"
      >
        <DialogTitle className="sr-only">Command palette</DialogTitle>
        <DialogDescription className="sr-only">Search commands or type a question</DialogDescription>
        <div className="flex items-center gap-2.5 border-b border-hairline px-3.5">
          <Command className="size-4 shrink-0 text-primary" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={ctx.hasScene ? "Ask this scene, or jump to a command…" : "Search commands…"}
            className="h-12 w-full bg-transparent text-[15px] text-ink outline-none ring-0 placeholder:text-mute focus:outline-none focus-visible:outline-none"
          />
        </div>
        <div ref={listRef} className="sq-scroll max-h-[min(400px,52vh)] overflow-y-auto p-1.5">
          {filtered.length === 0 ? (
            <p className="px-3 py-10 text-center text-[13px] text-mute">Nothing matches.</p>
          ) : (
            groups.map((group) => (
              <div key={group} className="mb-1.5">
                <div className="px-2.5 py-1.5 text-[10px] tracking-[0.14em] text-mute uppercase">{group}</div>
                {filtered
                  .filter((i) => i.group === group)
                  .map((item) => {
                    const index = filtered.indexOf(item);
                    const on = index === active;
                    return (
                      <button
                        key={item.id}
                        type="button"
                        data-pal={index}
                        disabled={item.disabled}
                        onMouseEnter={() => setActive(index)}
                        onClick={() => run(item)}
                        className={cn(
                          "relative flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px]",
                          on && "bg-raised",
                          item.disabled && "opacity-40",
                        )}
                      >
                        {on ? (
                          <span className="bg-primary absolute top-1.5 bottom-1.5 left-0 w-0.5 rounded-full" />
                        ) : null}
                        {item.thumb ? (
                          <img src={item.thumb} alt="" className="size-7 shrink-0 rounded-md object-cover" />
                        ) : (
                          <span className={cn("grid size-7 shrink-0 place-items-center rounded-md", on ? "text-primary" : "text-mute")}>
                            {item.icon}
                          </span>
                        )}
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-ink">
                            <Highlight text={item.label} q={query} />
                          </span>
                          {item.hint ? <span className="mt-0.5 block truncate text-[11px] text-mute">{item.hint}</span> : null}
                        </span>
                        {item.kbd ? <Kbd>{item.kbd}</Kbd> : null}
                      </button>
                    );
                  })}
              </div>
            ))
          )}
        </div>
        <div className="flex items-center gap-4 border-t border-hairline px-3.5 py-2 text-[11px] text-mute">
          <span className="inline-flex items-center gap-1.5">
            <Kbd>↑↓</Kbd> Move
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Kbd>
              <CornerDownLeft className="inline size-2.5" />
            </Kbd>
            Run
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Kbd>esc</Kbd> Close
          </span>
        </div>
      </DialogContent>
    </Dialog>
  );
}
