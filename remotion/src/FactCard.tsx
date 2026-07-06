import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { layoutStyles, type LayoutProps } from "./layout";

const DEFAULT_FACT_BACKGROUND =
  "linear-gradient(145deg, #071018 0%, #0f1c2b 55%, #132337 100%)";

export type FactCardProps = LayoutProps & {
  factNumber?: number | null;
  title?: string;
  body?: string;
  accentColor?: string;
  textColor?: string;
  bodyColor?: string;
  backgroundGradient?: string;
  fontFamily?: string;
  showFactBadge?: boolean;
  contentMaxWidth?: number;
  titleSize?: number;
  bodySize?: number;
  labelSize?: number;
  titleWeight?: number;
  lineHeight?: number;
  durationInFrames?: number;
};

export const FactCard: React.FC<FactCardProps> = ({
  factNumber = 1,
  title = "Fact",
  body = "",
  accentColor = "#5ecf8a",
  textColor = "#f4f7fb",
  bodyColor = "rgba(244,247,251,0.82)",
  backgroundGradient = DEFAULT_FACT_BACKGROUND,
  fontFamily = "Segoe UI, system-ui, sans-serif",
  showFactBadge = true,
  textAlign = "left",
  verticalAlign = "top",
  padding = 96,
  contentMaxWidth = 1400,
  titleSize = 68,
  bodySize = 34,
  labelSize = 28,
  titleWeight = 800,
  lineHeight = 1.45,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 200 } });
  const label = factNumber ? `Fact ${factNumber}` : "Fact";
  const layout = layoutStyles({ textAlign, verticalAlign, padding });

  return (
    <AbsoluteFill
      style={{
        background: backgroundGradient,
        color: textColor,
        fontFamily,
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
          maxWidth: contentMaxWidth,
        }}
      >
        {showFactBadge ? (
          <div
            style={{
              display: "inline-block",
              padding: "10px 18px",
              borderRadius: 999,
              background: "rgba(255,255,255,0.06)",
              border: `1px solid ${accentColor}`,
              color: accentColor,
              fontSize: labelSize,
              fontWeight: 700,
              letterSpacing: 1.2,
              textTransform: "uppercase",
            }}
          >
            {label}
          </div>
        ) : null}
        <h1
          style={{
            marginTop: showFactBadge ? 36 : 0,
            fontSize: titleSize,
            lineHeight: 1.1,
            fontWeight: titleWeight,
            maxWidth: contentMaxWidth,
          }}
        >
          {title}
        </h1>
        <p
          style={{
            marginTop: 28,
            fontSize: bodySize,
            lineHeight,
            color: bodyColor,
            maxWidth: contentMaxWidth,
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
