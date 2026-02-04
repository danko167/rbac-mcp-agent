import { createContext, type ReactNode } from "react";

export type LayoutSlotsContextValue = {
  left: ReactNode;
  setLeft: (node: ReactNode) => void;
  clearLeft: () => void;
};

export const LayoutSlotsContext =
  createContext<LayoutSlotsContextValue | null>(null);
