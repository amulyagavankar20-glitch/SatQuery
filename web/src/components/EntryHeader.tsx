import { Link, useRouterState } from "@tanstack/react-router";

import { Wordmark } from "@/components/Wordmark";
import { cn } from "@/lib/utils";

export function EntryHeader() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const onAbout = pathname === "/about";

  return (
    <header className="sq-header-glass relative z-20 flex h-12 w-full shrink-0 items-center gap-3 px-4 sm:px-6">
      <Wordmark />
      <Link
        to="/about"
        className={cn("sq-nav ml-auto", onAbout && "sq-nav-on")}
      >
        About
      </Link>
    </header>
  );
}
