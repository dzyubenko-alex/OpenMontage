import {AbsoluteFill, Audio, Img, Sequence, interpolate, useVideoConfig} from "remotion";
import {CaptionOverlay} from "../../components/CaptionOverlay";
import {resolveAsset} from "../../lib/resolveAsset";
import {narrationIsActiveAtFrame, SourceAudioTrack} from "../video-core-v1/VideoFrame";
import {VisualBoundary} from "../visualBoundaryTimeline";
import type {BrandingProfile} from "../photo-core-v1/types";
import {HybridFrame} from "./HybridFrame";
import {buildHybridTimeline, hybridTimelineDurationInFrames} from "./timeline";
import type {HybridCoreV1Props} from "./types";
const BrandLayer: React.FC<{profile: BrandingProfile}> = ({profile}) => {
  if (!profile.enabled || !profile.logo_src) return null;
  const vertical = profile.position.startsWith("top") ? {top: profile.safe_margin} : {bottom: profile.safe_margin};
  const horizontal = profile.position.endsWith("left") ? {left: profile.safe_margin} : {right: profile.safe_margin};
  return <Img src={resolveAsset(profile.logo_src)} style={{position: "absolute", maxWidth: profile.max_width,
    maxHeight: profile.max_width, objectFit: "contain", opacity: profile.opacity, ...vertical, ...horizontal}} />;
};
const EndCard: React.FC<{profile: BrandingProfile}> = ({profile}) => {
  const card = profile.end_card;
  if (!card?.enabled) return null;
  return <AbsoluteFill style={{backgroundColor: profile.primary_color, color: profile.text_color,
    fontFamily: profile.font_family, justifyContent: "center", alignItems: "center", textAlign: "center",
    padding: profile.safe_margin}}>
    <div style={{fontSize: profile.title_font_size, fontWeight: 700}}>{card.title}</div>
    {card.subtitle && <div style={{fontSize: profile.subtitle_font_size}}>{card.subtitle}</div>}
  </AbsoluteFill>;
};
export const HybridCoreV1: React.FC<HybridCoreV1Props> = ({cuts, profiles, audio, captions}) => {
  const {fps, durationInFrames} = useVideoConfig();
  const timeline = buildHybridTimeline(cuts, fps, profiles.editing);
  const contextualEnabled = profiles.editing.transition_mode === "contextual_v1";
  const narration = audio?.narration?.segments ?? (audio?.narration?.src ? [{src: audio.narration.src, start_seconds: 0}] : []);
  const voiceActive = profiles.voice.enabled && narration.length > 0;
  const visualEnd = hybridTimelineDurationInFrames(cuts, fps, profiles.editing);
  return <AbsoluteFill style={{backgroundColor: profiles.editing.background_color}}>
    {timeline.map((item, index) => <Sequence key={item.cut.id} from={item.startFrame}
      durationInFrames={item.durationInFrames} premountFor={fps}>
      {contextualEnabled ? <VisualBoundary item={item}>
        <HybridFrame item={item} editing={profiles.editing} profiles={profiles} narration={narration} index={index} />
      </VisualBoundary> :
        <HybridFrame item={item} editing={profiles.editing} profiles={profiles} narration={narration} index={index} />}
    </Sequence>)}
    {contextualEnabled && timeline.map((item) => item.cut.media_type === "video" ?
      <Sequence key={`source-audio-${item.cut.id}`} from={item.canonicalStartFrame}
        durationInFrames={item.semanticDurationInFrames} premountFor={fps}>
        <SourceAudioTrack cut={item.cut} sourceAudio={profiles.source_audio} narrationSegments={narration}
          timelineStartFrame={item.canonicalStartFrame} durationInFrames={item.semanticDurationInFrames} />
      </Sequence> : null)}
    {voiceActive && narration.map((segment, index) => {
      const from = Math.round((segment.start_seconds ?? 0) * fps);
      const duration = segment.end_seconds === undefined ? undefined
        : Math.max(1, Math.round((segment.end_seconds - (segment.start_seconds ?? 0)) * fps));
      return <Sequence key={`voice-${index}`} from={from} durationInFrames={duration} premountFor={fps}>
        <Audio src={resolveAsset(segment.src)} volume={profiles.voice.volume} />
      </Sequence>;
    })}
    {profiles.music.enabled && audio?.music?.src && <Audio
      src={resolveAsset(audio.music.src)} startFrom={Math.round((audio.music.offset_seconds ?? 0) * fps)}
      loop={profiles.music.loop} loopVolumeCurveBehavior="repeat"
      volume={(frame) => {
        const duck = profiles.music.ducking.enabled && voiceActive && narrationIsActiveAtFrame(frame, fps, narration)
          ? profiles.music.ducking.volume_multiplier : 1;
        const base = profiles.music.volume * duck;
        const fadeInFrames = profiles.music.fade_in_seconds * fps;
        const fadeOutFrames = profiles.music.fade_out_seconds * fps;
        const fadeIn = fadeInFrames > 0 ? interpolate(frame, [0, fadeInFrames], [0, base],
          {extrapolateLeft: "clamp", extrapolateRight: "clamp"}) : base;
        const fadeOut = fadeOutFrames > 0 ? interpolate(frame, [durationInFrames - fadeOutFrames, durationInFrames],
          [base, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"}) : base;
        return Math.min(fadeIn, fadeOut);
      }}
    />}
    {profiles.voice.captions.enabled && captions && captions.length > 0 && <CaptionOverlay
      words={captions} wordsPerPage={profiles.voice.captions.words_per_page}
      fontSize={profiles.voice.captions.font_size} color={profiles.branding.text_color}
      highlightColor={profiles.branding.primary_color} backgroundColor={profiles.branding.caption_background_color}
      fontFamily={profiles.branding.font_family}
    />}
    <BrandLayer profile={profiles.branding} />
    {profiles.branding.end_card?.enabled && <Sequence from={visualEnd}
      durationInFrames={Math.max(1, Math.round(profiles.branding.end_card.duration_seconds * fps))} premountFor={fps}>
      <EndCard profile={profiles.branding} />
    </Sequence>}
  </AbsoluteFill>;
};
