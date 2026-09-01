import {AbsoluteFill, Audio, Img, Sequence, interpolate, useVideoConfig} from "remotion";
import {CaptionOverlay} from "../../components/CaptionOverlay";
import {resolveAsset} from "../../lib/resolveAsset";
import {buildVideoTimeline, videoTimelineDurationSeconds} from "./timeline";
import {buildVisualBoundaryTimeline, VisualBoundary} from "../visualBoundaryTimeline";
import type {BrandingProfile} from "../photo-core-v1/types";
import type {VideoCoreV1Props} from "./types";
import {SourceAudioTrack, VideoFrame, narrationIsActiveAtFrame} from "./VideoFrame";
const BrandLayer: React.FC<{profile: BrandingProfile}> = ({profile}) => {
  if (!profile.enabled || !profile.logo_src) return null;
  const vertical = profile.position.startsWith("top") ? {top: profile.safe_margin} : {bottom: profile.safe_margin};
  const horizontal = profile.position.endsWith("left") ? {left: profile.safe_margin} : {right: profile.safe_margin};
  return <Img src={resolveAsset(profile.logo_src)} style={{
    position: "absolute", maxWidth: profile.max_width, maxHeight: profile.max_width,
    objectFit: "contain", opacity: profile.opacity, ...vertical, ...horizontal,
  }} />;
};
const EndCard: React.FC<{profile: BrandingProfile}> = ({profile}) => {
  const card = profile.end_card;
  if (!card?.enabled) return null;
  return <AbsoluteFill style={{
    backgroundColor: profile.primary_color, color: profile.text_color, fontFamily: profile.font_family,
    justifyContent: "center", alignItems: "center", textAlign: "center", padding: profile.safe_margin,
  }}>
    <div style={{fontSize: profile.title_font_size, fontWeight: 700}}>{card.title}</div>
    {card.subtitle && <div style={{fontSize: profile.subtitle_font_size}}>{card.subtitle}</div>}
  </AbsoluteFill>;
};
export const VideoCoreV1: React.FC<VideoCoreV1Props> = ({cuts, profiles, audio, captions}) => {
  const {fps, durationInFrames} = useVideoConfig();
  const timeline = buildVideoTimeline(cuts);
  const contextualEnabled = profiles.editing.transition_mode === "contextual_v1";
  const semanticDurations = timeline.map((clip) => Math.max(1, Math.round(clip.durationSeconds * fps)));
  const visualTimeline = buildVisualBoundaryTimeline(cuts, semanticDurations, fps, profiles.editing);
  const narration = audio?.narration?.segments ??
    (audio?.narration?.src ? [{src: audio.narration.src, start_seconds: 0}] : []);
  const voiceActive = profiles.voice.enabled && narration.length > 0;
  return <AbsoluteFill style={{backgroundColor: profiles.editing.background_color}}>
    {contextualEnabled ? visualTimeline.map((item) => {
      const visualCut = {...item.cut, transition_in: "cut" as const, transition_out: "cut" as const};
      return <Sequence key={item.cut.id} from={item.visualStartFrame} durationInFrames={item.visualDurationInFrames} premountFor={fps}>
        <VisualBoundary item={item}>
          <VideoFrame cut={visualCut} editing={profiles.editing} sourceAudio={profiles.source_audio}
            narrationSegments={narration} timelineStartFrame={item.canonicalStartFrame}
            durationInFrames={item.semanticDurationInFrames} visualOnly />
        </VisualBoundary>
      </Sequence>;
    }) : timeline.map((clip) => {
      const from = Math.round(clip.startSeconds * fps);
      const duration = Math.max(1, Math.round(clip.durationSeconds * fps));
      return <Sequence key={clip.cut.id} from={from} durationInFrames={duration} premountFor={fps}>
        <VideoFrame cut={clip.cut} editing={profiles.editing} sourceAudio={profiles.source_audio}
          narrationSegments={narration} timelineStartFrame={from} durationInFrames={duration} />
      </Sequence>;
    })}
    {contextualEnabled && timeline.map((clip) => {
      const from = Math.round(clip.startSeconds * fps);
      const duration = Math.max(1, Math.round(clip.durationSeconds * fps));
      return <Sequence key={`source-audio-${clip.cut.id}`} from={from} durationInFrames={duration} premountFor={fps}>
        <SourceAudioTrack cut={clip.cut} sourceAudio={profiles.source_audio} narrationSegments={narration}
          timelineStartFrame={from} durationInFrames={duration} />
      </Sequence>;
    })}
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
        const fadeOut = fadeOutFrames > 0 ? interpolate(frame,
          [durationInFrames - fadeOutFrames, durationInFrames], [base, 0],
          {extrapolateLeft: "clamp", extrapolateRight: "clamp"}) : base;
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
    {profiles.branding.end_card?.enabled && <Sequence from={Math.round(videoTimelineDurationSeconds(cuts) * fps)}
      durationInFrames={Math.max(1, Math.round(profiles.branding.end_card.duration_seconds * fps))} premountFor={fps}>
      <EndCard profile={profiles.branding} />
    </Sequence>}
  </AbsoluteFill>;
};
