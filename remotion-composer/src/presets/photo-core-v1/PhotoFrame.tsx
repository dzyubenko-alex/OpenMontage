import {
  AbsoluteFill,
  Img,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type {CSSProperties} from "react";
import {resolveAsset} from "../../lib/resolveAsset";
import {boundaryTransitionStyle, canonicalDirection, transitionPhaseIsActive} from "../contextualTransitions";
import {resolvePhotoBoundaryTransition} from "./legacyTransition";
import type {EditingProfile, PhotoCoreCut} from "./types";

type PhotoFrameProps = {
  cut: PhotoCoreCut;
  editing: EditingProfile;
  index: number;
};

const hardTransition = (value: string | undefined) =>
  value === "cut" || value === "none";

const motionFor = (cut: PhotoCoreCut, editing: EditingProfile, index: number) => {
  const explicit = cut.transform?.animation;
  if (explicit) return explicit;
  if (editing.motion === "alternate") return index % 2 === 0 ? "zoom-in" : "pan";
  return editing.motion;
};

export const cropViewportStyle = (
  crop: NonNullable<NonNullable<PhotoCoreCut["transform"]>["crop"]> | undefined,
): CSSProperties => crop
  ? {
      position: "absolute",
      left: crop.x,
      top: crop.y,
      width: crop.width,
      height: crop.height,
      overflow: "hidden",
    }
  : {
      position: "absolute",
      inset: 0,
      overflow: "hidden",
    };

export const PhotoFrame: React.FC<PhotoFrameProps> = ({cut, editing, index}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const durationInFrames = Math.max(1, Math.round((cut.out_seconds - cut.in_seconds) * fps));
  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const inFrames = Math.min(Math.round((cut.transition_in_duration ?? cut.transition_duration ?? editing.transition_seconds) * fps), Math.floor(durationInFrames / 2));
  const outFrames = Math.min(Math.round((cut.transition_out_duration ?? cut.transition_duration ?? editing.transition_seconds) * fps), Math.floor(durationInFrames / 2));
  const contextualEnabled = editing.transition_mode === "contextual_v1";
  const transitionIn = resolvePhotoBoundaryTransition({
    profileTransition: editing.transition, sceneTransition: cut.transition_in, contextualEnabled,
  });
  const transitionOut = resolvePhotoBoundaryTransition({
    profileTransition: editing.transition, sceneTransition: cut.transition_out, contextualEnabled,
  });
  const inActive = transitionPhaseIsActive({frame, durationInFrames, transitionFrames: inFrames, phase: "in"});
  const outActive = transitionPhaseIsActive({frame, durationInFrames, transitionFrames: outFrames, phase: "out"});
  const inStyle = boundaryTransitionStyle({transition: transitionIn, direction: canonicalDirection(cut.transition_in_direction), frame, durationInFrames, transitionFrames: inFrames, phase: "in"});
  const outStyle = boundaryTransitionStyle({transition: transitionOut, direction: canonicalDirection(cut.transition_out_direction), frame, durationInFrames, transitionFrames: outFrames, phase: "out"});
  const phaseStyle = outActive ? outStyle : inActive ? inStyle : {};

  const motion = motionFor(cut, editing, index);
  let scale = cut.transform?.scale ?? editing.scale_from;
  let x = 0;
  let y = 0;

  if (motion === "zoom" || motion === "zoom-in" || motion === "ken-burns" || motion === "ken-burns-slow-zoom") {
    scale = interpolate(progress, [0, 1], [editing.scale_from, editing.scale_to]);
  } else if (motion === "zoom-out") {
    scale = interpolate(progress, [0, 1], [editing.scale_to, editing.scale_from]);
  } else if (motion === "pan" || motion === "pan-left" || motion === "pan-right") {
    const direction = motion === "pan-right" || (motion === "pan" && index % 2 === 1) ? 1 : -1;
    x = interpolate(progress, [0, 1], [-editing.pan_x * direction, editing.pan_x * direction]);
    y = interpolate(progress, [0, 1], [-editing.pan_y, editing.pan_y]);
    scale = editing.scale_to;
  }

  const position = cut.transform?.position;
  const objectPosition = typeof position === "string"
    ? position
    : position
      ? `${position.x}% ${position.y}%`
      : "center";

  return (
    <AbsoluteFill style={{overflow: "hidden", backgroundColor: editing.background_color}}>
      <div style={{...cropViewportStyle(cut.transform?.crop), ...phaseStyle}}>
        <Img
          src={resolveAsset(cut.source)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: editing.image_fit,
            objectPosition,
            transform: `translate3d(${x}px, ${y}px, 0) scale(${scale})`,
            willChange: "transform, opacity",
          }}
        />
      </div>
    </AbsoluteFill>
  );
};
