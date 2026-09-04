export type Shortcut = { keys: string; mac?: string; label: string };

export const SHORTCUTS: Shortcut[] = [
  { keys: "Ctrl K", mac: "⌘K", label: "Command palette" },
  { keys: "/", label: "Focus composer" },
  { keys: "Ctrl Enter", mac: "⌘↵", label: "Send" },
  { keys: "Ctrl O", mac: "⌘O", label: "Attach GeoTIFF" },
  { keys: "1 – 5", label: "Official questions" },
  { keys: "F", label: "Fit scene" },
  { keys: "O", label: "Toggle optical" },
  { keys: "S", label: "Toggle SAR" },
  { keys: "G", label: "Toggle change" },
  { keys: "U", label: "Toggle uncertain" },
  { keys: "J", label: "Copy job id" },
  { keys: "I", label: "Inspect JSON" },
  { keys: "?", label: "Shortcuts" },
  { keys: "Esc", label: "Close overlay" },
];
