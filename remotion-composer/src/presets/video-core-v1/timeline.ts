import type {VideoCoreCut} from "./types";
export type VideoTimelineClip = {
  cut: VideoCoreCut; startSeconds: number; durationSeconds: number; playbackRate: number;
};
export const sourceDurationSeconds = (cut: VideoCoreCut) => cut.trim_out_seconds - cut.trim_in_seconds;
export const effectiveClipDurationSeconds = (cut: VideoCoreCut) => {
  const playbackRate = cut.playback_rate ?? 1;
  const available = sourceDurationSeconds(cut) / playbackRate;
  return cut.clip_duration_seconds === undefined ? available : Math.min(cut.clip_duration_seconds, available);
};
export const buildVideoTimeline = (cuts: VideoCoreCut[]): VideoTimelineClip[] => {
  let cursor = 0;
  return cuts.map((cut) => {
    const durationSeconds = effectiveClipDurationSeconds(cut);
    const clip = {cut, startSeconds: cursor, durationSeconds, playbackRate: cut.playback_rate ?? 1};
    cursor += durationSeconds;
    return clip;
  });
};
export const videoTimelineDurationSeconds = (cuts: VideoCoreCut[]) =>
  buildVideoTimeline(cuts).reduce((end, clip) => clip.startSeconds + clip.durationSeconds, 0);
