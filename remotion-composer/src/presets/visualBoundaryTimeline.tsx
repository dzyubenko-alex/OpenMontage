import type {ReactNode} from "react";
import {Freeze, useCurrentFrame} from "remotion";
import type {ContextualTransition, TransitionDirection, TransitionInput} from "./contextualTransitions";
import {boundaryTransitionStyle, canonicalDirection, canonicalTransition, transitionNeedsOverlap, transitionPhaseIsActive} from "./contextualTransitions";

export type BoundaryCut = {
  transition_in?: TransitionInput;
  transition_out?: TransitionInput;
  transition_duration?: number;
  transition_in_duration?: number;
  transition_out_duration?: number;
  transition_in_direction?: TransitionDirection;
  transition_out_direction?: TransitionDirection;
};

type BoundaryEditing = {
  transition: TransitionInput;
  transition_seconds: number;
  transition_mode?: "legacy" | "contextual_v1";
};

export type VisualBoundaryDecision = {
  fromIndex: number;
  toIndex: number;
  transition: ContextualTransition;
  durationInFrames: number;
  direction?: TransitionDirection;
};

export type VisualBoundaryItem<T> = {
  cut: T;
  canonicalStartFrame: number;
  semanticDurationInFrames: number;
  visualStartFrame: number;
  visualDurationInFrames: number;
  incomingBoundary?: VisualBoundaryDecision;
  outgoingBoundary?: VisualBoundaryDecision;
};

export const buildVisualBoundaries = <T extends BoundaryCut>(
  cuts: T[], durations: number[], fps: number, editing: BoundaryEditing,
): VisualBoundaryDecision[] => cuts.slice(1).map((right, index) => {
  const left = cuts[index];
  const transition = canonicalTransition(right.transition_in ?? left.transition_out ?? editing.transition);
  const seconds = right.transition_in_duration
    ?? left.transition_out_duration
    ?? right.transition_duration
    ?? left.transition_duration
    ?? editing.transition_seconds;
  const requested = transitionNeedsOverlap(transition) ? Math.max(0, Math.round(seconds * fps)) : 0;
  return {
    fromIndex: index,
    toIndex: index + 1,
    transition,
    durationInFrames: Math.min(requested, Math.floor(durations[index] / 2), Math.floor(durations[index + 1] / 2)),
    direction: canonicalDirection(right.transition_in_direction ?? left.transition_out_direction),
  };
});

export const buildVisualBoundaryTimeline = <T extends BoundaryCut>(
  cuts: T[], durations: number[], fps: number, editing: BoundaryEditing,
): VisualBoundaryItem<T>[] => {
  const canonicalStarts: number[] = [];
  let cursor = 0;
  durations.forEach((duration) => { canonicalStarts.push(cursor); cursor += duration; });
  const boundaries = buildVisualBoundaries(cuts, durations, fps, editing);
  return cuts.map((cut, index) => {
    const incomingBoundary = index === 0 ? undefined : boundaries[index - 1];
    const outgoingBoundary = index === cuts.length - 1 ? undefined : boundaries[index];
    const incomingFrames = incomingBoundary?.durationInFrames ?? 0;
    return {
      cut,
      canonicalStartFrame: canonicalStarts[index],
      semanticDurationInFrames: durations[index],
      visualStartFrame: canonicalStarts[index] - incomingFrames,
      visualDurationInFrames: durations[index] + incomingFrames,
      incomingBoundary,
      outgoingBoundary,
    };
  });
};

export const VisualBoundary: React.FC<{item: VisualBoundaryItem<BoundaryCut>; children: ReactNode}> = ({item, children}) => {
  const frame = useCurrentFrame();
  const incomingFrames = item.incomingBoundary?.durationInFrames ?? 0;
  const outgoingFrames = item.outgoingBoundary?.durationInFrames ?? 0;
  const incomingActive = transitionPhaseIsActive({frame, durationInFrames: item.visualDurationInFrames, transitionFrames: incomingFrames, phase: "in"});
  const outgoingActive = transitionPhaseIsActive({frame, durationInFrames: item.visualDurationInFrames, transitionFrames: outgoingFrames, phase: "out"});
  const incomingStyle = boundaryTransitionStyle({transition: item.incomingBoundary?.transition, direction: item.incomingBoundary?.direction, frame, durationInFrames: item.visualDurationInFrames, transitionFrames: incomingFrames, phase: "in"});
  const outgoingStyle = boundaryTransitionStyle({transition: item.outgoingBoundary?.transition, direction: item.outgoingBoundary?.direction, frame, durationInFrames: item.visualDurationInFrames, transitionFrames: outgoingFrames, phase: "out"});
  // Outgoing wins deterministically if a very short visual item makes phases overlap.
  const phaseStyle = outgoingActive ? outgoingStyle : incomingActive ? incomingStyle : {};
  const semanticFrame = Math.max(0, frame - incomingFrames);
  return <div style={{position: "absolute", inset: 0, overflow: "hidden", ...phaseStyle}}>
    <Freeze frame={semanticFrame}>{children}</Freeze>
  </div>;
};

export const visualTimelineDurationInFrames = <T,>(items: VisualBoundaryItem<T>[]) =>
  items.reduce((end, item) => Math.max(end, item.canonicalStartFrame + item.semanticDurationInFrames), 0);
