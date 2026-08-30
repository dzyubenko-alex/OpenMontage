import type {WordCaption} from "../../components/CaptionOverlay";
import type {BrandingProfile, ExportProfile, MusicProfile, VoiceProfile} from "../photo-core-v1/types";
export type SourceAudioMode = "muted" | "original";
export type VideoCoreTransition = "cut" | "fade";
export type VideoCoreCut = {
  id: string; source: string; trim_in_seconds: number; trim_out_seconds: number;
  clip_duration_seconds?: number; playback_rate?: number;
  source_audio?: SourceAudioMode; source_audio_volume?: number;
  transition_in?: VideoCoreTransition; transition_out?: VideoCoreTransition;
  transform?: {position?: string | {x: number; y: number}; crop?: {x: number; y: number; width: number; height: number}};
};
export type VideoEditingProfile = {
  transition: VideoCoreTransition; transition_seconds: number;
  video_fit: "cover" | "contain"; background_color: string;
};
export type SourceAudioProfile = {
  default_mode: SourceAudioMode; volume: number;
  ducking: {enabled: boolean; volume_multiplier: number};
};
export type VideoCoreProfiles = {
  voice: VoiceProfile; music: MusicProfile; editing: VideoEditingProfile;
  branding: BrandingProfile; export: ExportProfile; source_audio: SourceAudioProfile;
};
export type TimedAudioSource = {src: string; start_seconds?: number; end_seconds?: number};
export type VideoCoreAudio = {
  narration?: {src?: string; segments?: TimedAudioSource[]};
  music?: {src?: string; offset_seconds?: number};
};
export type VideoCoreV1Props = {
  cuts: VideoCoreCut[]; profiles: VideoCoreProfiles;
  audio?: VideoCoreAudio; captions?: WordCaption[];
};
