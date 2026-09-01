"use strict";
const fs = require("fs");
const path = require("path");
const ts = require("typescript");
const root = path.resolve(__dirname, "../..");

const interpolate = (value, input, output, options = {}) => {
  let ratio = (value - input[0]) / (input[1] - input[0]);
  if (options.extrapolateLeft === "clamp") ratio = Math.max(0, ratio);
  if (options.extrapolateRight === "clamp") ratio = Math.min(1, ratio);
  return output[0] + ratio * (output[1] - output[0]);
};
const compile = (relative, mocks) => {
  const source = fs.readFileSync(path.join(root, relative), "utf8");
  const js = ts.transpileModule(source, {compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
    jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true,
  }}).outputText;
  const module = {exports: {}};
  const localRequire = (name) => {
    if (Object.prototype.hasOwnProperty.call(mocks, name)) return mocks[name];
    return require(name);
  };
  new Function("require", "module", "exports", js)(localRequire, module, module.exports);
  return module.exports;
};
const transitions = compile("remotion-composer/src/presets/contextualTransitions.ts", {
  remotion: {interpolate},
});
const legacyPhoto = compile("remotion-composer/src/presets/photo-core-v1/legacyTransition.ts", {});
const legacyFixture = JSON.parse(fs.readFileSync(path.join(root, "tests/fixtures/contextual_transitions_v1/legacy_photo_profile_cut_scene_fade.json"), "utf8"));
const legacyEditing = legacyFixture.profiles.editing;
const legacyCut = legacyFixture.cuts[0];
if (legacyPhoto.resolvePhotoBoundaryTransition({
  profileTransition: legacyEditing.transition,
  sceneTransition: legacyCut.transition_in,
  contextualEnabled: false,
}) !== "cut") throw new Error("legacy PHOTO cut profile was overridden by scene fade");
if (legacyPhoto.resolvePhotoBoundaryTransition({
  profileTransition: legacyEditing.transition,
  sceneTransition: legacyCut.transition_in,
  contextualEnabled: true,
}) !== "fade") throw new Error("contextual PHOTO scene transition was changed");

const timeline = compile("remotion-composer/src/presets/visualBoundaryTimeline.tsx", {
  remotion: {Freeze: ({children}) => children, useCurrentFrame: () => 0},
  "./contextualTransitions": transitions,
  "react/jsx-runtime": {jsx: () => null, jsxs: () => null},
});
const assert = (condition, message) => { if (!condition) throw new Error(message); };
const editing = {transition: "crossfade", transition_seconds: 2, transition_mode: "contextual_v1"};
const cut = (media_type, extra = {}) => ({id: media_type, media_type, ...extra});

for (const [leftType, rightType] of [["photo","photo"],["video","video"],["photo","video"],["video","photo"]]) {
  const items = timeline.buildVisualBoundaryTimeline([cut(leftType), cut(rightType)], [10, 10], 10, editing);
  assert(items[0].incomingBoundary === undefined, "first scene acquired incoming boundary");
  assert(items[1].outgoingBoundary === undefined, "last scene acquired outgoing boundary");
  assert(items[0].outgoingBoundary === items[1].incomingBoundary, "boundary is not shared source of truth");
  assert(items[0].outgoingBoundary.durationInFrames === 5, "long transition was not clamped");
  assert(items[0].visualStartFrame === 0 && items[1].visualStartFrame === 5, "overlap frame range mismatch");
  const coverage = Array.from({length: 20}, (_, frame) =>
    items.some((item) => frame >= item.visualStartFrame && frame < item.visualStartFrame + item.visualDurationInFrames));
  assert(coverage.every(Boolean), "blank visual frame in boundary timeline");
  for (let frame = 5; frame < 10; frame++) {
    const out = transitions.boundaryTransitionStyle({transition: "crossfade", frame, durationInFrames: 10, transitionFrames: 5, phase: "out"});
    const incoming = transitions.boundaryTransitionStyle({transition: "crossfade", frame: frame - 5, durationInFrames: 15, transitionFrames: 5, phase: "in"});
    assert(Math.abs((out.opacity ?? 1) + (incoming.opacity ?? 1) - 1) < 1e-9, "crossfade creates black/bright frame");
  }
}

const shortItems = timeline.buildVisualBoundaryTimeline([cut("photo"), cut("video"), cut("photo")], [4, 4, 4], 10, editing);
assert(shortItems[0].outgoingBoundary.durationInFrames === 2, "short left scene clamp failed");
assert(shortItems[1].incomingBoundary.durationInFrames === 2, "short incoming duration failed");
assert(shortItems[1].outgoingBoundary.durationInFrames === 2, "short outgoing duration failed");
assert(shortItems[2].incomingBoundary.durationInFrames === 2, "last boundary duration failed");

for (const type of transitions.SUPPORTED_TRANSITIONS) {
  const style = transitions.boundaryTransitionStyle({transition: type, direction: "up", frame: 1, durationInFrames: 10, transitionFrames: 4, phase: "in"});
  if (type === "hard_cut") assert(Object.keys(style).length === 0, "hard cut rendered decoration");
  else assert(style.opacity !== undefined, type + " did not render overlap opacity");
}
for (const direction of transitions.TRANSITION_DIRECTIONS) {
  const style = transitions.boundaryTransitionStyle({transition: "directional_push", direction, frame: 1, durationInFrames: 10, transitionFrames: 4, phase: "in"});
  if (direction === "up" || direction === "down") assert(/translate3d\(0%/.test(style.transform), direction + " did not use Y axis");
  else assert(/, 0%, 0\)/.test(style.transform), direction + " did not use X axis");
}
const steady = transitions.boundaryTransitionStyle({transition: "section_transition", frame: 5, durationInFrames: 12, transitionFrames: 3, phase: "in"});
assert(Object.keys(steady).length === 0, "incoming transform leaked into steady phase");
console.log("contextual timeline runtime: PASS");
