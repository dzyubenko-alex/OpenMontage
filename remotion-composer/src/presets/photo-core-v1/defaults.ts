import type {PhotoCoreV1Props} from "./types";

export const photoCoreV1DefaultProps = {
  cuts: [],
  profiles: {
    voice: {
      enabled: false,
      volume: 1,
      captions: {enabled: false, words_per_page: 6, font_size: 42},
    },
    music: {
      enabled: false,
      volume: 0.1,
      fade_in_seconds: 2,
      fade_out_seconds: 3,
      loop: false,
      ducking: {enabled: false, volume_multiplier: 1},
    },
    editing: {
      motion: "alternate",
      transition: "fade",
      transition_seconds: 0.35,
      image_fit: "cover",
      background_color: "#000000",
      scale_from: 1,
      scale_to: 1.08,
      pan_x: 24,
      pan_y: 12,
    },
    branding: {
      enabled: false,
      position: "top-right",
      opacity: 1,
      max_width: 240,
      safe_margin: 48,
      primary_color: "#FFFFFF",
      text_color: "#FFFFFF",
      caption_background_color: "rgba(0, 0, 0, 0.72)",
      font_family: "Inter",
      title_font_size: 72,
      subtitle_font_size: 34,
    },
    export: {
      media_profile: "generic_hd",
      preview: {
        enabled: false,
        root: "",
        mode: "PHOTO",
        filename_template: "{project}-{mode}-{timestamp}.{ext}",
        timestamp_format: "%Y%m%d-%H%M%S",
        on_conflict: "increment",
        failure_policy: "warn",
      },
    },
  },
  audio: {},
  captions: [],
} satisfies PhotoCoreV1Props;
