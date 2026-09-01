import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {CaptionOverlay} from "../../components/CaptionOverlay";
import {resolveAsset} from "../../lib/resolveAsset";
import {PhotoFrame} from "./PhotoFrame";
import {buildVisualBoundaryTimeline, VisualBoundary} from "../visualBoundaryTimeline";
import type {BrandingProfile, PhotoCoreV1Props} from "./types";

const positionStyle = (profile: BrandingProfile): React.CSSProperties => ({
  top: profile.position.startsWith("top") ? profile.safe_margin : undefined,
  bottom: profile.position.startsWith("bottom") ? profile.safe_margin : undefined,
  left: profile.position.endsWith("left") ? profile.safe_margin : undefined,
  right: profile.position.endsWith("right") ? profile.safe_margin : undefined,
});

export const narrationIsActiveAtFrame = (
  frame: number,
  fps: number,
  segments: NonNullable<NonNullable<PhotoCoreV1Props["audio"]>["narration"]>["segments"],
) => (segments ?? []).some((segment) => {
  const startFrame = Math.round((segment.start_seconds ?? 0) * fps);
  const endFrame = segment.end_seconds === undefined
    ? Number.POSITIVE_INFINITY
    : Math.round(segment.end_seconds * fps);
  return frame >= startFrame && frame < endFrame;
});

const BrandLayer: React.FC<{profile: BrandingProfile}> = ({profile}) => {
  if (!profile.enabled || !profile.logo_src) return null;
  return (
    <Img
      src={resolveAsset(profile.logo_src)}
      style={{
        position: "absolute",
        maxWidth: profile.max_width,
        maxHeight: profile.max_width,
        objectFit: "contain",
        opacity: profile.opacity,
        ...positionStyle(profile),
      }}
    />
  );
};

const EndCard: React.FC<{
  profile: BrandingProfile;
  fadeSeconds: number;
  durationFrames: number;
}> = ({profile, fadeSeconds, durationFrames}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const fadeFrames = Math.min(Math.round(fadeSeconds * fps), Math.floor(durationFrames / 3));
  const opacity = fadeFrames > 0
    ? Math.min(
        interpolate(frame, [0, fadeFrames], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"}),
        interpolate(frame, [durationFrames - fadeFrames, durationFrames], [1, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"}),
      )
    : 1;
  const endCard = profile.end_card;
  if (!endCard?.enabled) return null;
  return (
    <AbsoluteFill style={{
      backgroundColor: profile.primary_color,
      color: profile.text_color,
      fontFamily: profile.font_family,
      justifyContent: "center",
      alignItems: "center",
      textAlign: "center",
      opacity,
      padding: profile.safe_margin,
    }}>
      <div style={{fontSize: profile.title_font_size, fontWeight: 700}}>{endCard.title}</div>
      {endCard.subtitle && <div style={{fontSize: profile.subtitle_font_size, marginTop: profile.safe_margin / 2}}>{endCard.subtitle}</div>}
    </AbsoluteFill>
  );
};

export const PhotoCoreV1: React.FC<PhotoCoreV1Props> = ({cuts, profiles, audio, captions}) => {
  const {fps, durationInFrames} = useVideoConfig();
  const visualEnd = cuts.reduce((max, cut) => Math.max(max, cut.out_seconds), 0);
  const contextualEnabled = profiles.editing.transition_mode === "contextual_v1";
  const semanticDurations = cuts.map((cut) => Math.max(1, Math.round((cut.out_seconds - cut.in_seconds) * fps)));
  const visualTimeline = buildVisualBoundaryTimeline(cuts, semanticDurations, fps, profiles.editing);
  const narrationSegments = audio?.narration?.segments ?? (
    audio?.narration?.src ? [{src: audio.narration.src, start_seconds: 0}] : []
  );
  const music = audio?.music;
  const voiceActive = profiles.voice.enabled && narrationSegments.length > 0;
  const musicBaseVolume = profiles.music.volume;

  return (
    <AbsoluteFill style={{backgroundColor: profiles.editing.background_color}}>
      {contextualEnabled ? visualTimeline.map((item, index) => {
        const visualCut = {...item.cut, transition_in: "cut" as const, transition_out: "cut" as const};
        return <Sequence key={item.cut.id} from={item.visualStartFrame} durationInFrames={item.visualDurationInFrames} premountFor={fps}>
          <VisualBoundary item={item}>
            <PhotoFrame cut={visualCut} editing={profiles.editing} index={index} />
          </VisualBoundary>
        </Sequence>;
      }) : cuts.map((cut, index) => {
        const from = Math.round(cut.in_seconds * fps);
        const duration = Math.max(1, Math.round((cut.out_seconds - cut.in_seconds) * fps));
        return (
          <Sequence key={cut.id} from={from} durationInFrames={duration} premountFor={fps}>
            <PhotoFrame cut={cut} editing={profiles.editing} index={index} />
          </Sequence>
        );
      })}

      {voiceActive && narrationSegments.map((segment, index) => {
        const from = Math.round((segment.start_seconds ?? 0) * fps);
        const duration = segment.end_seconds === undefined
          ? undefined
          : Math.max(1, Math.round((segment.end_seconds - (segment.start_seconds ?? 0)) * fps));
        return (
          <Sequence key={`voice-${index}`} from={from} durationInFrames={duration} premountFor={fps}>
            <Audio src={resolveAsset(segment.src)} volume={profiles.voice.volume} />
          </Sequence>
        );
      })}

      {profiles.music.enabled && music?.src && (
        <Audio
          src={resolveAsset(music.src)}
          startFrom={Math.round((music.offset_seconds ?? 0) * fps)}
          loop={profiles.music.loop}
          loopVolumeCurveBehavior="repeat"
          volume={(frame) => {
            const narrationActive = voiceActive && narrationIsActiveAtFrame(
              frame,
              fps,
              narrationSegments,
            );
            const duckingMultiplier = profiles.music.ducking.enabled && narrationActive
              ? profiles.music.ducking.volume_multiplier
              : 1;
            const frameVolume = musicBaseVolume * duckingMultiplier;
            const fadeInFrames = profiles.music.fade_in_seconds * fps;
            const fadeOutFrames = profiles.music.fade_out_seconds * fps;
            const fadeIn = fadeInFrames > 0
              ? interpolate(frame, [0, fadeInFrames], [0, frameVolume], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})
              : frameVolume;
            const fadeOut = fadeOutFrames > 0
              ? interpolate(frame, [durationInFrames - fadeOutFrames, durationInFrames], [frameVolume, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})
              : frameVolume;
            return Math.min(fadeIn, fadeOut);
          }}
        />
      )}

      {profiles.voice.captions.enabled && captions && captions.length > 0 && (
        <CaptionOverlay
          words={captions}
          wordsPerPage={profiles.voice.captions.words_per_page}
          fontSize={profiles.voice.captions.font_size}
          color={profiles.branding.text_color}
          highlightColor={profiles.branding.primary_color}
          backgroundColor={profiles.branding.caption_background_color}
          fontFamily={profiles.branding.font_family}
        />
      )}

      <BrandLayer profile={profiles.branding} />

      {profiles.branding.end_card?.enabled && (
        <Sequence
          from={Math.round(visualEnd * fps)}
          durationInFrames={Math.max(1, Math.round(profiles.branding.end_card.duration_seconds * fps))}
          premountFor={fps}
        >
          <EndCard
            profile={profiles.branding}
            fadeSeconds={profiles.editing.transition_seconds}
            durationFrames={Math.max(1, Math.round(profiles.branding.end_card.duration_seconds * fps))}
          />
        </Sequence>
      )}
    </AbsoluteFill>
  );
};
