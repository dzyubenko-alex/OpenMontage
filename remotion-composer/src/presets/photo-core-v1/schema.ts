import {z} from "zod";

const boundedVolume = z.number().min(0).max(1);

export const photoCoreV1Schema = z.object({
  cuts: z.array(z.object({
    id: z.string(),
    source: z.string(),
    in_seconds: z.number().min(0),
    out_seconds: z.number().min(0),
    transition_in: z.string().optional(),
    transition_out: z.string().optional(),
    transform: z.object({
      animation: z.string().optional(),
      scale: z.number().positive().optional(),
      position: z.union([
        z.string(),
        z.object({x: z.number(), y: z.number()}),
      ]).optional(),
      crop: z.object({
        x: z.number(), y: z.number(), width: z.number().positive(), height: z.number().positive(),
      }).optional(),
    }).optional(),
  }).refine((cut) => cut.out_seconds > cut.in_seconds, {
    message: "out_seconds must be greater than in_seconds",
  })),
  profiles: z.object({
    voice: z.object({
      enabled: z.boolean(),
      volume: boundedVolume,
      captions: z.object({
        enabled: z.boolean(),
        words_per_page: z.number().int().positive(),
        font_size: z.number().int().positive(),
      }),
    }),
    music: z.object({
      enabled: z.boolean(),
      volume: boundedVolume,
      fade_in_seconds: z.number().min(0),
      fade_out_seconds: z.number().min(0),
      loop: z.boolean(),
      ducking: z.object({enabled: z.boolean(), volume_multiplier: boundedVolume}),
    }),
    editing: z.object({
      motion: z.enum(["static", "zoom", "pan", "alternate"]),
      transition: z.enum(["cut", "fade"]),
      transition_seconds: z.number().min(0),
      image_fit: z.enum(["cover", "contain"]),
      background_color: z.string(),
      scale_from: z.number().positive(),
      scale_to: z.number().positive(),
      pan_x: z.number(),
      pan_y: z.number(),
    }),
    branding: z.object({
      enabled: z.boolean(),
      logo_src: z.string().optional(),
      position: z.enum(["top-left", "top-right", "bottom-left", "bottom-right"]),
      opacity: boundedVolume,
      max_width: z.number().positive(),
      safe_margin: z.number().min(0),
      primary_color: z.string(),
      text_color: z.string(),
      caption_background_color: z.string(),
      font_family: z.string(),
      title_font_size: z.number().positive(),
      subtitle_font_size: z.number().positive(),
      end_card: z.object({
        enabled: z.boolean(),
        title: z.string(),
        subtitle: z.string().optional(),
        duration_seconds: z.number().min(0),
      }).optional(),
    }),
    export: z.object({
      media_profile: z.string().min(1),
      width: z.number().int().positive().optional(),
      height: z.number().int().positive().optional(),
      fps: z.number().int().positive().optional(),
    }),
  }),
  audio: z.object({
    narration: z.object({
      src: z.string().optional(),
      segments: z.array(z.object({
        src: z.string(),
        start_seconds: z.number().min(0).optional(),
        end_seconds: z.number().min(0).optional(),
      })).optional(),
    }).optional(),
    music: z.object({
      src: z.string().optional(),
      offset_seconds: z.number().min(0).optional(),
    }).optional(),
  }).optional(),
  captions: z.array(z.object({
    word: z.string(),
    startMs: z.number(),
    endMs: z.number(),
    pageBreakAfter: z.boolean().optional(),
  })).optional(),
});
