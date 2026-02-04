import { useContext } from "react";
import { LayoutSlotsContext, type LayoutSlotsContextValue } from "./LayoutSlotsContext";

export function useLayoutSlots(): LayoutSlotsContextValue {
  const ctx = useContext(LayoutSlotsContext);
  if (!ctx) {
    throw new Error("useLayoutSlots must be used within LayoutSlotsProvider");
  }
  return ctx;
}
