import {interpolate} from "remotion";
import type {CSSProperties} from "react";

export const SUPPORTED_TRANSITIONS = ["hard_cut", "crossfade", "subtle_zoom", "directional_push", "matched_motion", "section_transition"] as const;
export const LEGACY_TRANSITION_INPUTS = ["cut", "fade"] as const;
export const TRANSITION_INPUTS = [...SUPPORTED_TRANSITIONS, ...LEGACY_TRANSITION_INPUTS] as const;
export const TRANSITION_DIRECTIONS = ["left", "right", "up", "down"] as const;
export type ContextualTransition = typeof SUPPORTED_TRANSITIONS[number];
export type TransitionDirection = typeof TRANSITION_DIRECTIONS[number];
export type TransitionInput = typeof TRANSITION_INPUTS[number];

export const canonicalTransition = (value: TransitionInput | undefined): ContextualTransition => {
  if (!value || value === "fade") return "crossfade";
  if (value === "cut") return "hard_cut";
  return SUPPORTED_TRANSITIONS.includes(value as ContextualTransition) ? value as ContextualTransition : "hard_cut";
};

export const canonicalDirection = (value: TransitionDirection | undefined): TransitionDirection | undefined =>
  TRANSITION_DIRECTIONS.includes(value as TransitionDirection) ? value as TransitionDirection : undefined;

export const transitionNeedsOverlap = (value: TransitionInput | undefined) => canonicalTransition(value) !== "hard_cut";

export const transitionPhaseIsActive = ({frame, durationInFrames, transitionFrames, phase}: {
  frame: number; durationInFrames: number; transitionFrames: number; phase: "in" | "out";
}) => transitionFrames > 0 && (phase === "in"
  ? frame >= 0 && frame < transitionFrames
  : frame >= durationInFrames - transitionFrames && frame < durationInFrames);

const motionVector = (direction: TransitionDirection | undefined) => {
  if (direction === "right") return {x: 1, y: 0};
  if (direction === "up") return {x: 0, y: -1};
  if (direction === "down") return {x: 0, y: 1};
  return {x: -1, y: 0};
};

export const boundaryTransitionStyle = ({transition, direction, frame, durationInFrames, transitionFrames, phase}: {
  transition: TransitionInput | undefined;
  direction?: TransitionDirection;
  frame: number;
  durationInFrames: number;
  transitionFrames: number;
  phase: "in" | "out";
}): CSSProperties => {
  const type = canonicalTransition(transition);
  if (type === "hard_cut" || !transitionPhaseIsActive({frame, durationInFrames, transitionFrames, phase})) return {};
  const progress = phase === "in"
    ? interpolate(frame, [0, transitionFrames], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})
    : interpolate(frame, [durationInFrames - transitionFrames, durationInFrames], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  const visibility = phase === "in" ? progress : 1 - progress;
  if (type === "crossfade") return {opacity: visibility};
  if (type === "subtle_zoom") {
    const scale = phase === "in" ? 1.012 - progress * 0.012 : 1 + progress * 0.012;
    return {opacity: visibility, transform: `scale(${scale})`};
  }
  const vector = motionVector(direction);
  const amount = type === "directional_push" ? 3.5 : type === "matched_motion" ? 1.5 : 1.5;
  const signedProgress = phase === "in" ? -(1 - progress) : progress;
  const translate = `translate3d(${vector.x * signedProgress * amount}%, ${vector.y * signedProgress * amount}%, 0)`;
  if (type === "matched_motion") {
    const scale = phase === "in" ? 1.006 - progress * 0.006 : 1 + progress * 0.006;
    return {opacity: visibility, transform: `${translate} scale(${scale})`};
  }
  return {opacity: visibility, transform: translate};
};
