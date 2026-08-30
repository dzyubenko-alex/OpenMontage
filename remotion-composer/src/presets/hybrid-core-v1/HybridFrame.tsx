import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import {PhotoFrame} from "../photo-core-v1/PhotoFrame";
import {VideoFrame} from "../video-core-v1/VideoFrame";
import type {PhotoCoreCut} from "../photo-core-v1/types";
import type {TimedAudioSource, VideoCoreCut} from "../video-core-v1/types";
import type {HybridEditingProfile, HybridProfiles} from "./types";
import type {HybridTimelineItem} from "./timeline";
type Props = {item: HybridTimelineItem; editing: HybridEditingProfile; profiles: HybridProfiles; narration: TimedAudioSource[]; index: number};
export const HybridFrame: React.FC<Props> = ({item, editing, profiles, narration, index}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const fadeIn = item.fadeInFrames > 0
    ? interpolate(frame, [0, item.fadeInFrames], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"}) : 1;
  const fadeOut = item.fadeOutFrames > 0
    ? interpolate(frame, [item.durationInFrames - item.fadeOutFrames, item.durationInFrames], [1, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"}) : 1;
  const opacity = Math.min(fadeIn, fadeOut);
  if (item.cut.media_type === "photo") {
    const cut: PhotoCoreCut = {
      ...item.cut, in_seconds: 0, out_seconds: item.durationInFrames / fps,
      transition_in: "cut", transition_out: "cut",
    };
    return <AbsoluteFill style={{opacity}}><PhotoFrame cut={cut} editing={editing} index={index} /></AbsoluteFill>;
  }
  const cut: VideoCoreCut = {...item.cut, transition_in: "cut", transition_out: "cut"};
  return <AbsoluteFill style={{opacity}}><VideoFrame
    cut={cut} editing={editing} sourceAudio={profiles.source_audio} narrationSegments={narration}
    timelineStartFrame={item.startFrame} durationInFrames={item.durationInFrames}
  /></AbsoluteFill>;
};
