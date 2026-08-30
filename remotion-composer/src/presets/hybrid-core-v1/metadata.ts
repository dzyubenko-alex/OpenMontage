import type {CalculateMetadataFunction} from "remotion";
import {hybridTimelineDurationInFrames} from "./timeline";
import type {HybridCoreV1Props} from "./types";
export const calculateHybridCoreV1Metadata: CalculateMetadataFunction<HybridCoreV1Props> = ({props}) => {
  const fps = props.profiles.export.fps ?? 30;
  const visual = hybridTimelineDurationInFrames(props.cuts, fps, props.profiles.editing);
  const card = props.profiles.branding.end_card;
  const endCard = card?.enabled ? Math.round(card.duration_seconds * fps) : 0;
  return {durationInFrames: Math.max(1, visual + endCard), fps, width: props.profiles.export.width, height: props.profiles.export.height};
};
