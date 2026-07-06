import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { layoutStyles, type LayoutProps } from "./layout";

export type TitleCardProps = LayoutProps & {
  title?: string;
  subtitle?: string;
  accentColor?: string;
  titleSize?: number;
  subtitleSize?: number;
  durationInFrames?: number;
};

export const TitleCard: React.FC<TitleCardProps> = ({
  title = "Title",
  subtitle = "",
  accentColor = "#7db7ff",
  textAlign = "center",
  verticalAlign = "center",
  padding = 120,
  titleSize = 84,
  subtitleSize = 36,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 180 } });
  const layout = layoutStyles({ textAlign, verticalAlign, padding });

  return (
    <AbsoluteFill
      style={{
        background:
          "radial-gradient(circle at 20% 20%, rgba(125,183,255,0.18), transparent 35%), linear-gradient(160deg, #05070d 0%, #10182a 100%)",
        color: "#f8fbff",
        fontFamily: "Segoe UI, system-ui, sans-serif",
        display: "flex",
        flexDirection: "column",
        ...layout.container,
      }}
    >
      <div
        style={{
          transform: `scale(${0.92 + enter * 0.08})`,
          opacity: enter,
          ...layout.content,
        }}
      >
        <div
          style={{
            width: 120,
            height: 6,
            borderRadius: 999,
            background: accentColor,
            margin: textAlign === "center" ? "0 auto 36px" : "0 0 36px",
            opacity: interpolate(frame, [0, 12], [0, 1], {
              extrapolateRight: "clamp",
            }),
          }}
        />
        <h1
          style={{
            fontSize: titleSize,
            lineHeight: 1.05,
            fontWeight: 800,
            letterSpacing: -1.5,
          }}
        >
          {title}
        </h1>
        {subtitle ? (
          <p
            style={{
              marginTop: 28,
              fontSize: subtitleSize,
              lineHeight: 1.4,
              color: "rgba(248,251,255,0.78)",
            }}
          >
            {subtitle}
          </p>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
