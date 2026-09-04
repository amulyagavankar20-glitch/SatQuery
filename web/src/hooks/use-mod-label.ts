import { useEffect, useState } from "react";

export function useModLabel() {
  const [mac, setMac] = useState(false);
  useEffect(() => {
    setMac(/Mac|iPhone|iPad/.test(navigator.platform) || /Mac OS/.test(navigator.userAgent));
  }, []);
  return mac ? "⌘" : "Ctrl";
}
