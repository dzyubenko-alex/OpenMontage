import type {WordCaption} from "../../components/CaptionOverlay";
import type {BrandingProfile, ExportProfile, MusicProfile, VoiceProfile} from "../photo-core-v1/types";
import type {SourceAudioProfile, TimedAudioSource} from "../video-core-v1/types";
export type HybridTransition = "cut" | "fade";
export type HybridTransform = {position?: string | {x: number; y: number}; crop?: {x: number; y: number; width: number; height: number}};
export type HybridPhotoCut = {media_type: "photo"; id: string; source: string; duration_seconds: number; transition_in?: HybridTransition; transition_out?: HybridTransition; transform?: HybridTransform & {animation?: string; scale?: number}};
export type HybridVideoCut = {media_type: "video"; id: string; source: string; trim_in_seconds: number; trim_out_seconds: number; clip_duration_seconds?: number; playback_rate?: number; source_audio?: "muted" | "original"; source_audio_volume?: number; transition_in?: HybridTransition; transition_out?: HybridTransition; transform?: HybridTransform};
export type HybridCut = HybridPhotoCut | HybridVideoCut;
export type HybridEditingProfile = {motion: "static" | "zoom" | "pan" | "alternate"; transition: HybridTransition; transition_seconds: number; image_fit: "cover" | "contain"; video_fit: "cover" | "contain"; background_color: string; scale_from: number; scale_to: number; pan_x: number; pan_y: number};
export type HybridExportProfile = Omit<ExportProfile, "preview"> & {
  preview?: Omit<NonNullable<ExportProfile["preview"]>, "mode"> & {mode: "HYBRID"};
};
export type HybridProfiles = {voice: VoiceProfile; music: MusicProfile; editing: HybridEditingProfile; branding: BrandingProfile; export: HybridExportProfile; source_audio: SourceAudioProfile};
export type HybridAudio = {narration?: {src?: string; segments?: TimedAudioSource[]}; music?: {src?: string; offset_seconds?: number}};
export type HybridCoreV1Props = {cuts: HybridCut[]; profiles: HybridProfiles; audio?: HybridAudio; captions?: WordCaption[]};
