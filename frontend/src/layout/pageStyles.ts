import type { CSSProperties } from "react";

export const fullHeightStackStyle: CSSProperties = {
  height: "100%",
  minHeight: 0,
};

export const fullHeightPaperStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  minHeight: 0,
  height: "100%",
};

export const fullHeightFlexStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  flex: 1,
  minHeight: 0,
};

export const scrollBodyStyle: CSSProperties = {
  marginTop: 12,
  flex: 1,
  minHeight: 0,
  overflow: "auto",
};
