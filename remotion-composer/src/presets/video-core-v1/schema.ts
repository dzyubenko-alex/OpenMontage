import {z} from "zod";
import {transitionDirectionSchema, transitionInputSchema} from "../transitionSchema";
const volume = z.number().min(0).max(1);
const audioMode = z.enum(["muted", "original"]);
export const videoCoreV1Schema = z.object({
  cuts: z.array(z.object({
    id: z.string(), source: z.string(),
    trim_in_seconds: z.number().min(0), trim_out_seconds: z.number().min(0),
    clip_duration_seconds: z.number().positive().optional(),
    playback_rate: z.number().positive().optional(),
    source_audio: audioMode.optional(), source_audio_volume: volume.optional(),
    transition_in: transitionInputSchema.optional(),
    transition_out: transitionInputSchema.optional(),
    transition_duration: z.number().min(0).optional(),
    transition_in_duration: z.number().min(0).optional(), transition_out_duration: z.number().min(0).optional(),
    transition_in_direction: transitionDirectionSchema.optional(), transition_out_direction: transitionDirectionSchema.optional(),
    transform: z.object({
      position: z.union([z.string(), z.object({x: z.number(), y: z.number()})]).optional(),
      crop: z.object({x: z.number(), y: z.number(), width: z.number().positive(), height: z.number().positive()}).optional(),
    }).optional(),
  }).refine((cut) => cut.trim_out_seconds > cut.trim_in_seconds, {
    message: "trim_out_seconds must be greater than trim_in_seconds",
  })),
  profiles: z.object({
    voice: z.object({
      enabled: z.boolean(), volume,
      captions: z.object({enabled: z.boolean(), words_per_page: z.number().int().positive(), font_size: z.number().int().positive()}),
    }),
    music: z.object({
      enabled: z.boolean(), volume, fade_in_seconds: z.number().min(0), fade_out_seconds: z.number().min(0),
      loop: z.boolean(), ducking: z.object({enabled: z.boolean(), volume_multiplier: volume}),
    }),
    editing: z.object({
      transition: transitionInputSchema, transition_seconds: z.number().min(0), transition_mode: z.enum(["legacy", "contextual_v1"]).optional(),
      video_fit: z.enum(["cover", "contain"]), background_color: z.string(),
    }),
    branding: z.object({
      enabled: z.boolean(), logo_src: z.string().optional(),
      position: z.enum(["top-left", "top-right", "bottom-left", "bottom-right"]),
      opacity: volume, max_width: z.number().positive(), safe_margin: z.number().min(0),
      primary_color: z.string(), text_color: z.string(), caption_background_color: z.string(),
      font_family: z.string(), title_font_size: z.number().positive(), subtitle_font_size: z.number().positive(),
      end_card: z.object({enabled: z.boolean(), title: z.string(), subtitle: z.string().optional(), duration_seconds: z.number().min(0)}).optional(),
    }),
    export: z.object({
      media_profile: z.string().min(1), width: z.number().int().positive().optional(),
      height: z.number().int().positive().optional(), fps: z.number().int().positive().optional(),
      preview: z.object({
        enabled: z.boolean().default(false), root: z.string(), mode: z.enum(["PHOTO", "VIDEO", "HYBRID"]),
        filename_template: z.string(), timestamp_format: z.string(), on_conflict: z.enum(["increment", "error"]),
        failure_policy: z.enum(["warn", "error"]),
      }).optional(),
    }),
    source_audio: z.object({
      default_mode: audioMode.default("muted"), volume,
      ducking: z.object({enabled: z.boolean(), volume_multiplier: volume}),
    }),
  }),
  audio: z.object({
    narration: z.object({src: z.string().optional(), segments: z.array(z.object({
      src: z.string(), start_seconds: z.number().min(0).optional(), end_seconds: z.number().min(0).optional(),
    })).optional()}).optional(),
    music: z.object({src: z.string().optional(), offset_seconds: z.number().min(0).optional()}).optional(),
  }).optional(),
  captions: z.array(z.object({word: z.string(), startMs: z.number(), endMs: z.number(), pageBreakAfter: z.boolean().optional()})).optional(),
});
