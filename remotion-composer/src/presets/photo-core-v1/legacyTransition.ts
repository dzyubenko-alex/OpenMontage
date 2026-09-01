import type {TransitionInput} from "../contextualTransitions";

export const resolvePhotoBoundaryTransition = ({
  profileTransition,
  sceneTransition,
  contextualEnabled,
}: {
  profileTransition: TransitionInput;
  sceneTransition?: TransitionInput;
  contextualEnabled: boolean;
}): TransitionInput => {
  if (contextualEnabled) return sceneTransition ?? profileTransition;
  if (profileTransition === "cut") return "cut";
  if (profileTransition === "fade") {
    return sceneTransition === "cut" || sceneTransition === "hard_cut" ? "cut" : "fade";
  }
  return sceneTransition ?? profileTransition;
};
