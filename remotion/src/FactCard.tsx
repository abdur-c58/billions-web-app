import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { layoutStyles, type LayoutProps } from "./layout";

export type FactCardProps = LayoutProps & {
  factNumber?: number | null;
  title?: string;
  body?: string;
  accentColor?: string;
  titleSize?: number;
  bodySize?: number;
  durationInFrames?: number;
};

export const FactCard: React.FC<FactCardProps> = ({
  factNumber = 1,
  title = "Fact",
  body = "",
  accentColor = "#5ecf8a",
  textAlign = "left",
  verticalAlign = "top",
  padding = 96,
  titleSize = 68,
  bodySize = 34,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 200 } });
  const label = factNumber ? `Fact ${factNumber}` : "Fact";
  const layout = layoutStyles({ textAlign, verticalAlign, padding });

  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(145deg, #071018 0%, #0f1c2b 55%, #132337 100%)",
        color: "#f4f7fb",
        fontFamily: "Segoe UI, system-ui, sans-serif",
        display: "flex",
        flexDirection: "column",
        ...layout.container,
      }}
    >
      <div
        style={{
          transform: `translateY(${(1 - enter) * 40}px)`,
          opacity: enter,
          ...layout.content,
        }}
      >
        <div
          style={{
            display: "inline-block",
            padding: "10px 18px",
            borderRadius: 999,
            background: "rgba(255,255,255,0.06)",
            border: `1px solid ${accentColor}`,
            color: accentColor,
            fontSize: 28,
            fontWeight: 700,
            letterSpacing: 1.2,
            textTransform: "uppercase",
          }}
        >
          {label}
        </div>
        <h1
          style={{
            marginTop: 36,
            fontSize: titleSize,
            lineHeight: 1.1,
            fontWeight: 800,
            maxWidth: 1200,
          }}
        >
          {title}
        </h1>
        <p
          style={{
            marginTop: 28,
            fontSize: bodySize,
            lineHeight: 1.45,
            color: "rgba(244,247,251,0.82)",
            maxWidth: 1180,
            opacity: interpolate(frame, [8, 24], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          {body}
        </p>
      </div>
    </AbsoluteFill>
  );
};
