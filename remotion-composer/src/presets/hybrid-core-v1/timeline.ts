import type {HybridCut, HybridEditingProfile} from "./types";
export type HybridTimelineItem = {cut: HybridCut; startFrame: number; durationInFrames: number; fadeInFrames: number; fadeOutFrames: number};
export const hybridCutDurationInFrames = (cut: HybridCut, fps: number) => {
  if (cut.media_type === "photo") return Math.max(1, Math.round(cut.duration_seconds * fps));
  const rate = cut.playback_rate ?? 1;
  const available = (cut.trim_out_seconds - cut.trim_in_seconds) / rate;
  const seconds = cut.clip_duration_seconds === undefined ? available : Math.min(cut.clip_duration_seconds, available);
  return Math.max(1, Math.round(seconds * fps));
};
export const boundaryTransition = (left: HybridCut, right: HybridCut, editing: HybridEditingProfile) => right.transition_in ?? left.transition_out ?? editing.transition;
export const buildHybridTimeline = (cuts: HybridCut[], fps: number, editing: HybridEditingProfile): HybridTimelineItem[] => {
  const items: HybridTimelineItem[] = [];
  for (const cut of cuts) {
    const durationInFrames = hybridCutDurationInFrames(cut, fps);
    if (items.length === 0) { items.push({cut, startFrame: 0, durationInFrames, fadeInFrames: 0, fadeOutFrames: 0}); continue; }
    const previous = items[items.length - 1];
    const requested = boundaryTransition(previous.cut, cut, editing) === "fade" ? Math.round(editing.transition_seconds * fps) : 0;
    const overlap = Math.max(0, Math.min(requested, Math.floor(previous.durationInFrames / 2), Math.floor(durationInFrames / 2)));
    previous.fadeOutFrames = overlap;
    items.push({cut, startFrame: previous.startFrame + previous.durationInFrames - overlap, durationInFrames, fadeInFrames: overlap, fadeOutFrames: 0});
  }
  return items;
};
export const hybridTimelineDurationInFrames = (cuts: HybridCut[], fps: number, editing: HybridEditingProfile) => {
  const timeline = buildHybridTimeline(cuts, fps, editing);
  const last = timeline[timeline.length - 1];
  return last ? last.startFrame + last.durationInFrames : 0;
};
