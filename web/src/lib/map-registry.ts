type FitFn = () => void;

let latest: FitFn | null = null;

export function registerMapFit(fn: FitFn): () => void {
  latest = fn;
  return () => {
    if (latest === fn) latest = null;
  };
}

export function fitLatestMap() {
  latest?.();
}
