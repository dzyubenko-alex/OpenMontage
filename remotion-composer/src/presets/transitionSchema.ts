import {z} from "zod";
import {TRANSITION_DIRECTIONS, TRANSITION_INPUTS} from "./contextualTransitions";

export const transitionInputSchema = z.enum(TRANSITION_INPUTS);
export const transitionDirectionSchema = z.enum(TRANSITION_DIRECTIONS);
export const motionHintSchema = z.object({
  direction: transitionDirectionSchema,
}).strict();

export type MotionHint = z.infer<typeof motionHintSchema>;
