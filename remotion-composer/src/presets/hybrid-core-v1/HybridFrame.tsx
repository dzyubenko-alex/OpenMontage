import {AbsoluteFill, useCurrentFrame, useVideoConfig} from "remotion";
import {boundaryTransitionStyle, canonicalDirection, transitionPhaseIsActive} from "../contextualTransitions";
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
  const contextualEnabled = editing.transition_mode === "contextual_v1";
  const inFrames = item.fadeInFrames ?? 0;
  const outFrames = item.fadeOutFrames ?? 0;
  const inActive = transitionPhaseIsActive({frame, durationInFrames: item.durationInFrames, transitionFrames: inFrames, phase: "in"});
  const outActive = transitionPhaseIsActive({frame, durationInFrames: item.durationInFrames, transitionFrames: outFrames, phase: "out"});
  const inStyle = boundaryTransitionStyle({transition: item.transitionIn, direction: canonicalDirection(item.cut.transition_in_direction), frame, durationInFrames: item.durationInFrames, transitionFrames: inFrames, phase: "in"});
  const outStyle = boundaryTransitionStyle({transition: item.transitionOut, direction: canonicalDirection(item.cut.transition_out_direction), frame, durationInFrames: item.durationInFrames, transitionFrames: outFrames, phase: "out"});
  const boundaryStyle = contextualEnabled ? {} : outActive ? outStyle : inActive ? inStyle : {};
  if (item.cut.media_type === "photo") {
    const cut: PhotoCoreCut = {...item.cut, in_seconds: 0, out_seconds: item.semanticDurationInFrames / fps, transition_in: "cut", transition_out: "cut"};
    return <AbsoluteFill style={boundaryStyle}><PhotoFrame cut={cut} editing={editing} index={index} /></AbsoluteFill>;
  }
  const cut: VideoCoreCut = {...item.cut, transition_in: "cut", transition_out: "cut"};
  return <AbsoluteFill style={boundaryStyle}><VideoFrame cut={cut} editing={editing} sourceAudio={profiles.source_audio} narrationSegments={narration} timelineStartFrame={item.canonicalStartFrame} durationInFrames={item.semanticDurationInFrames} visualOnly={contextualEnabled} /></AbsoluteFill>;
};
