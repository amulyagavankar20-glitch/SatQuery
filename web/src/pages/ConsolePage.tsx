import { AppShell } from "@/components/AppShell";
import { Composer } from "@/components/Composer";
import { Thread } from "@/components/Thread";

export function ConsolePage() {
  return (
    <AppShell>
      <Thread />
      <Composer />
    </AppShell>
  );
}
