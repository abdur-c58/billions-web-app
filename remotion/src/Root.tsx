import React from "react";
import { Composition } from "remotion";
import { FactCard, type FactCardProps } from "./FactCard";
import { TitleCard, type TitleCardProps } from "./TitleCard";

const FPS = 30;
const DEFAULT_FRAMES = 150;

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="FactCard"
        component={FactCard}
        durationInFrames={DEFAULT_FRAMES}
        fps={FPS}
        width={1920}
        height={1080}
        defaultProps={{
          factNumber: 1,
          title: "Sample fact",
          body: "Remotion fact card preview.",
          accentColor: "#5ecf8a",
        }}
        calculateMetadata={({ props }) => ({
          durationInFrames: Math.max(
            30,
            Number((props as FactCardProps).durationInFrames) || DEFAULT_FRAMES,
          ),
        })}
      />
      <Composition
        id="TitleCard"
        component={TitleCard}
        durationInFrames={DEFAULT_FRAMES}
        fps={FPS}
        width={1920}
        height={1080}
        defaultProps={{
          title: "Title",
          subtitle: "Subtitle",
          accentColor: "#7db7ff",
        }}
        calculateMetadata={({ props }) => ({
          durationInFrames: Math.max(
            30,
            Number((props as TitleCardProps).durationInFrames) || DEFAULT_FRAMES,
          ),
        })}
      />
    </>
  );
};
