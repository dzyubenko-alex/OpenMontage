import {AbsoluteFill, Audio, OffthreadVideo, interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import type {CSSProperties} from "react";
import {resolveAsset} from "../../lib/resolveAsset";
import {boundaryTransitionStyle, canonicalDirection, canonicalTransition, transitionPhaseIsActive} from "../contextualTransitions";
import type {SourceAudioProfile, TimedAudioSource, VideoCoreCut, VideoEditingProfile} from "./types";

export const cropViewportStyle = (crop: NonNullable<NonNullable<VideoCoreCut["transform"]>["crop"]> | undefined): CSSProperties =>
  crop ? {position: "absolute", left: crop.x, top: crop.y, width: crop.width, height: crop.height, overflow: "hidden"}
    : {position: "absolute", inset: 0, overflow: "hidden"};
export const narrationIsActiveAtFrame = (frame: number, fps: number, segments: TimedAudioSource[]) =>
  segments.some((segment) => {
    const start = Math.round((segment.start_seconds ?? 0) * fps);
    const end = segment.end_seconds === undefined ? Number.POSITIVE_INFINITY : Math.round(segment.end_seconds * fps);
    return frame >= start && frame < end;
  });
export const resolveSourceAudioMode = (cut: VideoCoreCut, profile: SourceAudioProfile) =>
  cut.source_audio ?? profile.default_mode;
export const sourceAudioVolumeAtFrame = (
  cut: VideoCoreCut, profile: SourceAudioProfile, narrationActive: boolean,
) => {
  if (resolveSourceAudioMode(cut, profile) === "muted") return 0;
  const base = cut.source_audio_volume ?? profile.volume;
  return base * (profile.ducking.enabled && narrationActive ? profile.ducking.volume_multiplier : 1);
};

type Props = {
  cut: VideoCoreCut; editing: VideoEditingProfile; sourceAudio: SourceAudioProfile;
  narrationSegments: TimedAudioSource[]; timelineStartFrame: number; durationInFrames: number; visualOnly?: boolean;
};
export const VideoFrame: React.FC<Props> = ({
  cut, editing, sourceAudio, narrationSegments, timelineStartFrame, durationInFrames, visualOnly = false,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const inFrames = Math.min(Math.round((cut.transition_in_duration ?? cut.transition_duration ?? editing.transition_seconds) * fps), Math.floor(durationInFrames / 2));
  const outFrames = Math.min(Math.round((cut.transition_out_duration ?? cut.transition_duration ?? editing.transition_seconds) * fps), Math.floor(durationInFrames / 2));
  const fadeInEnabled = canonicalTransition(cut.transition_in ?? editing.transition) !== "hard_cut";
  const fadeOutEnabled = canonicalTransition(cut.transition_out ?? editing.transition) !== "hard_cut";
  const inActive = transitionPhaseIsActive({frame, durationInFrames, transitionFrames: inFrames, phase: "in"});
  const outActive = transitionPhaseIsActive({frame, durationInFrames, transitionFrames: outFrames, phase: "out"});
  const inStyle = boundaryTransitionStyle({transition: fadeInEnabled ? cut.transition_in ?? editing.transition : "hard_cut", direction: canonicalDirection(cut.transition_in_direction), frame, durationInFrames, transitionFrames: inFrames, phase: "in"});
  const outStyle = boundaryTransitionStyle({transition: fadeOutEnabled ? cut.transition_out ?? editing.transition : "hard_cut", direction: canonicalDirection(cut.transition_out_direction), frame, durationInFrames, transitionFrames: outFrames, phase: "out"});
  const boundaryStyle = outActive ? outStyle : inActive ? inStyle : {};
  const position = cut.transform?.position;
  const objectPosition = typeof position === "string" ? position : position ? `${position.x}% ${position.y}%` : "center";
  const globalFrame = timelineStartFrame + frame;
  const originalVolume = sourceAudioVolumeAtFrame(
    cut, sourceAudio, narrationIsActiveAtFrame(globalFrame, fps, narrationSegments),
  );
  const trimBefore = Math.round(cut.trim_in_seconds * fps);
  const playableSourceFrames = Math.round(durationInFrames * (cut.playback_rate ?? 1));

  return (
    <AbsoluteFill style={{backgroundColor: editing.background_color, ...boundaryStyle}}>
      <div style={cropViewportStyle(cut.transform?.crop)}>
        <OffthreadVideo
          src={resolveAsset(cut.source)}
          startFrom={trimBefore}
          endAt={Math.min(Math.round(cut.trim_out_seconds * fps), trimBefore + playableSourceFrames)}
          playbackRate={cut.playback_rate ?? 1}
          muted={visualOnly || resolveSourceAudioMode(cut, sourceAudio) === "muted"}
          volume={visualOnly ? 0 : originalVolume}
          style={{width: "100%", height: "100%", objectFit: editing.video_fit, objectPosition}}
        />
      </div>
    </AbsoluteFill>
  );
};

export const SourceAudioTrack: React.FC<Omit<Props, "editing" | "visualOnly">> = ({
  cut, sourceAudio, narrationSegments, timelineStartFrame, durationInFrames,
}) => {
  const {fps} = useVideoConfig();
  if (resolveSourceAudioMode(cut, sourceAudio) === "muted") return null;
  const trimBefore = Math.round(cut.trim_in_seconds * fps);
  const playableSourceFrames = Math.round(durationInFrames * (cut.playback_rate ?? 1));
  return <Audio
    src={resolveAsset(cut.source)}
    startFrom={trimBefore}
    endAt={Math.min(Math.round(cut.trim_out_seconds * fps), trimBefore + playableSourceFrames)}
    playbackRate={cut.playback_rate ?? 1}
    volume={(frame) => sourceAudioVolumeAtFrame(
      cut, sourceAudio, narrationIsActiveAtFrame(timelineStartFrame + frame, fps, narrationSegments),
    )}
  />;
};
