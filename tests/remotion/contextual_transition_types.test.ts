import type {Cut} from "../../remotion-composer/src/Explainer";
import type {TransitionInput} from "../../remotion-composer/src/presets/contextualTransitions";

const valid: TransitionInput[] = [
  "cut", "fade", "hard_cut", "crossfade", "subtle_zoom",
  "directional_push", "matched_motion", "section_transition",
];
const cut: Pick<Cut, "transition_in" | "transition_out"> = {
  transition_in: valid[0],
  transition_out: valid[1],
};
void cut;

// @ts-expect-error arbitrary public transition must be rejected
const wipe: Pick<Cut, "transition_in"> = {transition_in: "wipe"};
// @ts-expect-error arbitrary public transition must be rejected
const zoomFast: TransitionInput = "zoom_fast";
// @ts-expect-error arbitrary public transition must be rejected
const randomTransition: Pick<Cut, "transition_out"> = {transition_out: "random_transition"};
void wipe; void zoomFast; void randomTransition;
