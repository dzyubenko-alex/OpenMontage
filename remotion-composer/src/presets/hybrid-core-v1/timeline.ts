import {canonicalTransition, transitionNeedsOverlap} from "../contextualTransitions";
import type {ContextualTransition} from "../contextualTransitions";
import {buildVisualBoundaryTimeline} from "../visualBoundaryTimeline";
import type {VisualBoundaryItem} from "../visualBoundaryTimeline";
import type {HybridCut, HybridEditingProfile} from "./types";
export type HybridTimelineItem = VisualBoundaryItem<HybridCut> & {
  startFrame: number; durationInFrames: number;
  fadeInFrames?: number; fadeOutFrames?: number;
  transitionIn?: ContextualTransition; transitionOut?: ContextualTransition;
};
export const hybridCutDurationInFrames = (cut: HybridCut, fps: number) => {
  if (cut.media_type === "photo") return Math.max(1, Math.round(cut.duration_seconds * fps));
  const rate = cut.playback_rate ?? 1;
  const available = (cut.trim_out_seconds - cut.trim_in_seconds) / rate;
  const seconds = cut.clip_duration_seconds === undefined ? available : Math.min(cut.clip_duration_seconds, available);
  return Math.max(1, Math.round(seconds * fps));
};
export const boundaryTransition = (left: HybridCut, right: HybridCut, editing: HybridEditingProfile) => canonicalTransition(right.transition_in ?? left.transition_out ?? editing.transition);
export const buildHybridTimeline = (cuts: HybridCut[], fps: number, editing: HybridEditingProfile): HybridTimelineItem[] => {
  const durations = cuts.map((cut) => hybridCutDurationInFrames(cut, fps));
  if (editing.transition_mode === "contextual_v1") {
    return buildVisualBoundaryTimeline(cuts, durations, fps, editing).map((item) => ({
      ...item, startFrame: item.visualStartFrame, durationInFrames: item.visualDurationInFrames,
    }));
  }
  const items: HybridTimelineItem[] = [];
  let canonicalCursor = 0;
  for (const cut of cuts) {
    const semanticDurationInFrames = hybridCutDurationInFrames(cut, fps);
    if (items.length === 0) {
      items.push({cut, startFrame: 0, durationInFrames: semanticDurationInFrames, canonicalStartFrame: 0,
        semanticDurationInFrames, visualStartFrame: 0, visualDurationInFrames: semanticDurationInFrames,
        fadeInFrames: 0, fadeOutFrames: 0, transitionIn: "hard_cut", transitionOut: "hard_cut"});
      canonicalCursor += semanticDurationInFrames; continue;
    }
    const previous = items[items.length - 1];
    const transition = boundaryTransition(previous.cut, cut, editing);
    const seconds = cut.transition_duration ?? previous.cut.transition_duration ?? editing.transition_seconds;
    const requested = transitionNeedsOverlap(transition) ? Math.round(seconds * fps) : 0;
    const overlap = Math.max(0, Math.min(requested, Math.floor(previous.semanticDurationInFrames / 2), Math.floor(semanticDurationInFrames / 2)));
    previous.fadeOutFrames = overlap; previous.transitionOut = transition;
    const startFrame = previous.startFrame + previous.durationInFrames - overlap;
    items.push({cut, startFrame, durationInFrames: semanticDurationInFrames, canonicalStartFrame: canonicalCursor,
      semanticDurationInFrames, visualStartFrame: startFrame, visualDurationInFrames: semanticDurationInFrames,
      fadeInFrames: overlap, fadeOutFrames: 0, transitionIn: transition, transitionOut: "hard_cut"});
    canonicalCursor += semanticDurationInFrames;
  }
  return items;
};
export const hybridTimelineDurationInFrames = (cuts: HybridCut[], fps: number, editing: HybridEditingProfile) => {
  if (editing.transition_mode === "contextual_v1") return cuts.reduce((sum, cut) => sum + hybridCutDurationInFrames(cut, fps), 0);
  const timeline = buildHybridTimeline(cuts, fps, editing);
  const last = timeline[timeline.length - 1];
  return last ? last.startFrame + last.durationInFrames : 0;
};
