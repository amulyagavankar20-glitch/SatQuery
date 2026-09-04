import { useNavigate } from "@tanstack/react-router";
import { History } from "lucide-react";

import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { formatClock } from "@/lib/utils";
import { useConsole } from "@/state/console";

export function JobsDrawer() {
  const { jobs, jobsOpen, closeJobs, restoreJob } = useConsole();
  const navigate = useNavigate();

  return (
    <Sheet open={jobsOpen} onOpenChange={(open) => (open ? undefined : closeJobs())}>
      <SheetContent side="right">
        <SheetHeader>
          <SheetTitle>Jobs</SheetTitle>
          <SheetDescription>Last runs. Click to restore.</SheetDescription>
        </SheetHeader>
        <div className="sq-scroll min-h-0 flex-1 overflow-y-auto px-4 pb-6">
          {jobs.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-16 text-center">
              <History className="size-6 text-mute" />
              <p className="text-[13px] text-mute">No runs yet.</p>
            </div>
          ) : (
            <ul className="flex flex-col gap-1">
              {jobs.map((job) => (
                <li key={job.id}>
                  <button
                    type="button"
                    onClick={() => {
                      restoreJob(job.id);
                      void navigate({ to: "/" });
                    }}
                    className="hover:bg-raised w-full rounded-xl px-3 py-3 text-left"
                  >
                    <div className="line-clamp-2 text-[13px] leading-snug text-ink">{job.query}</div>
                    <div className="mt-1.5 truncate text-[11px] text-mute">
                      {formatClock(job.createdAt)}
                      {job.summary ? ` · ${job.summary}` : ""}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
