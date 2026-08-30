import {AbsoluteFill, OffthreadVideo, interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import type {CSSProperties} from "react";
import {resolveAsset} from "../../lib/resolveAsset";
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
  narrationSegments: TimedAudioSource[]; timelineStartFrame: number; durationInFrames: number;
};
export const VideoFrame: React.FC<Props> = ({
  cut, editing, sourceAudio, narrationSegments, timelineStartFrame, durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const transitionFrames = Math.min(Math.round(editing.transition_seconds * fps), Math.floor(durationInFrames / 2));
  const fadeInEnabled = (cut.transition_in ?? editing.transition) === "fade";
  const fadeOutEnabled = (cut.transition_out ?? editing.transition) === "fade";
  const fadeIn = fadeInEnabled && transitionFrames > 0
    ? interpolate(frame, [0, transitionFrames], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"}) : 1;
  const fadeOut = fadeOutEnabled && transitionFrames > 0
    ? interpolate(frame, [durationInFrames - transitionFrames, durationInFrames], [1, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"}) : 1;
  const position = cut.transform?.position;
  const objectPosition = typeof position === "string" ? position : position ? `${position.x}% ${position.y}%` : "center";
  const globalFrame = timelineStartFrame + frame;
  const originalVolume = sourceAudioVolumeAtFrame(
    cut, sourceAudio, narrationIsActiveAtFrame(globalFrame, fps, narrationSegments),
  );
  const trimBefore = Math.round(cut.trim_in_seconds * fps);
  const playableSourceFrames = Math.round(durationInFrames * (cut.playback_rate ?? 1));

  return (
    <AbsoluteFill style={{backgroundColor: editing.background_color, opacity: Math.min(fadeIn, fadeOut)}}>
      <div style={cropViewportStyle(cut.transform?.crop)}>
        <OffthreadVideo
          src={resolveAsset(cut.source)}
          startFrom={trimBefore}
          endAt={Math.min(Math.round(cut.trim_out_seconds * fps), trimBefore + playableSourceFrames)}
          playbackRate={cut.playback_rate ?? 1}
          muted={resolveSourceAudioMode(cut, sourceAudio) === "muted"}
          volume={originalVolume}
          style={{width: "100%", height: "100%", objectFit: editing.video_fit, objectPosition}}
        />
      </div>
    </AbsoluteFill>
  );
};
