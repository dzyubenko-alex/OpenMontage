import type {WordCaption} from "../../components/CaptionOverlay";

export type PhotoCoreMotion = "static" | "zoom" | "pan" | "alternate";
export type PhotoCoreTransition = "cut" | "fade";

export type PhotoCoreCut = {
  id: string;
  source: string;
  in_seconds: number;
  out_seconds: number;
  transition_in?: string;
  transition_out?: string;
  transform?: {
    animation?: string;
    scale?: number;
    position?: string | {x: number; y: number};
    crop?: {x: number; y: number; width: number; height: number};
  };
};

export type VoiceProfile = {
  enabled: boolean;
  volume: number;
  captions: {enabled: boolean; words_per_page: number; font_size: number};
};

export type MusicProfile = {
  enabled: boolean;
  volume: number;
  fade_in_seconds: number;
  fade_out_seconds: number;
  loop: boolean;
  ducking: {enabled: boolean; volume_multiplier: number};
};

export type EditingProfile = {
  motion: PhotoCoreMotion;
  transition: PhotoCoreTransition;
  transition_seconds: number;
  image_fit: "cover" | "contain";
  background_color: string;
  scale_from: number;
  scale_to: number;
  pan_x: number;
  pan_y: number;
};

export type BrandingProfile = {
  enabled: boolean;
  logo_src?: string;
  position: "top-left" | "top-right" | "bottom-left" | "bottom-right";
  opacity: number;
  max_width: number;
  safe_margin: number;
  primary_color: string;
  text_color: string;
  caption_background_color: string;
  font_family: string;
  title_font_size: number;
  subtitle_font_size: number;
  end_card?: {
    enabled: boolean;
    title: string;
    subtitle?: string;
    duration_seconds: number;
  };
};

export type ExportProfile = {
  media_profile: string;
  width?: number;
  height?: number;
  fps?: number;
};

export type PhotoCoreProfiles = {
  voice: VoiceProfile;
  music: MusicProfile;
  editing: EditingProfile;
  branding: BrandingProfile;
  export: ExportProfile;
};

export type TimedAudioSource = {
  src: string;
  start_seconds?: number;
  end_seconds?: number;
};

export type PhotoCoreAudio = {
  narration?: {src?: string; segments?: TimedAudioSource[]};
  music?: {src?: string; offset_seconds?: number};
};

export type PhotoCoreV1Props = {
  cuts: PhotoCoreCut[];
  profiles: PhotoCoreProfiles;
  audio?: PhotoCoreAudio;
  captions?: WordCaption[];
};
