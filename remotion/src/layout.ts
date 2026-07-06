import type { CSSProperties } from "react";

export type TextAlign = "left" | "center" | "right";
export type VerticalAlign = "top" | "center" | "bottom";

export type LayoutProps = {
  textAlign?: TextAlign;
  verticalAlign?: VerticalAlign;
  padding?: number;
};

export function layoutStyles({
  textAlign = "left",
  verticalAlign = "top",
  padding = 96,
}: LayoutProps) {
  const justifyContent =
    verticalAlign === "center"
      ? "center"
      : verticalAlign === "bottom"
        ? "flex-end"
        : "flex-start";

  return {
    container: {
      padding,
      justifyContent,
      alignItems: textAlign === "center" ? "center" : "stretch",
    } as CSSProperties,
    content: {
      textAlign,
      width: textAlign === "center" ? "100%" : undefined,
      maxWidth: textAlign === "center" ? 1500 : 1400,
    } as CSSProperties,
  };
}
