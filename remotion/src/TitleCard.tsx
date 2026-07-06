import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { layoutStyles, type LayoutProps } from "./layout";

const DEFAULT_TITLE_BACKGROUND =
  "radial-gradient(circle at 20% 20%, rgba(125,183,255,0.18), transparent 35%), linear-gradient(160deg, #05070d 0%, #10182a 100%)";

export type TitleCardProps = LayoutProps & {
  title?: string;
  subtitle?: string;
  accentColor?: string;
  textColor?: string;
  subtitleColor?: string;
  backgroundGradient?: string;
  fontFamily?: string;
  showAccentBar?: boolean;
  contentMaxWidth?: number;
  titleSize?: number;
  subtitleSize?: number;
  titleWeight?: number;
  lineHeight?: number;
  durationInFrames?: number;
};

export const TitleCard: React.FC<TitleCardProps> = ({
  title = "Title",
  subtitle = "",
  accentColor = "#7db7ff",
  textColor = "#f8fbff",
  subtitleColor = "rgba(248,251,255,0.78)",
  backgroundGradient = DEFAULT_TITLE_BACKGROUND,
  fontFamily = "Segoe UI, system-ui, sans-serif",
  showAccentBar = true,
  textAlign = "center",
  verticalAlign = "center",
  padding = 120,
  contentMaxWidth = 1500,
  titleSize = 84,
  subtitleSize = 36,
  titleWeight = 800,
  lineHeight = 1.4,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 180 } });
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
          transform: `scale(${0.92 + enter * 0.08})`,
          opacity: enter,
          ...layout.content,
          maxWidth: contentMaxWidth,
        }}
      >
        {showAccentBar ? (
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
        ) : null}
        <h1
          style={{
            fontSize: titleSize,
            lineHeight: 1.05,
            fontWeight: titleWeight,
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
              lineHeight,
              color: subtitleColor,
            }}
          >
            {subtitle}
          </p>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
