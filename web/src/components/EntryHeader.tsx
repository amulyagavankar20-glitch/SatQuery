import { Link, useRouterState } from "@tanstack/react-router";

import { Wordmark } from "@/components/Wordmark";
import { cn } from "@/lib/utils";

const prefetchAbout = () => {
  const img = new Image();
  img.src = "/about-plate.jpg";
};

export function EntryHeader() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const onAbout = pathname === "/about";

  return (
    <header className="sq-header-glass relative z-20 flex h-12 w-full shrink-0 items-center gap-3 px-4 sm:px-6">
      <Wordmark />
      <Link
        to="/about"
        onMouseEnter={prefetchAbout}
        onFocus={prefetchAbout}
        className={cn("sq-nav ml-auto transition-all duration-150 active:scale-95", onAbout && "sq-nav-on")}
      >
        About
      </Link>
    </header>
  );
}
