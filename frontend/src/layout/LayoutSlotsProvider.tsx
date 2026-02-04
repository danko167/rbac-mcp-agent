import { type ReactNode, useCallback, useMemo, useState } from "react";
import { LayoutSlotsContext, type LayoutSlotsContextValue } from "./LayoutSlotsContext";

export function LayoutSlotsProvider({ children }: { children: ReactNode }) {
  const [left, setLeftState] = useState<ReactNode>(null);

  const setLeft = useCallback((node: ReactNode) => {
    setLeftState(node);
  }, []);

  const clearLeft = useCallback(() => {
    setLeftState(null);
  }, []);

  const value = useMemo<LayoutSlotsContextValue>(() => {
    return { left, setLeft, clearLeft };
  }, [left, setLeft, clearLeft]);

  return (
    <LayoutSlotsContext.Provider value={value}>
      {children}
    </LayoutSlotsContext.Provider>
  );
}
