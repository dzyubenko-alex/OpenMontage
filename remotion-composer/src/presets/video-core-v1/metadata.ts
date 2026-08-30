import type {CalculateMetadataFunction} from "remotion";
import {videoTimelineDurationSeconds} from "./timeline";
import type {VideoCoreV1Props} from "./types";
export const calculateVideoCoreV1Metadata: CalculateMetadataFunction<VideoCoreV1Props> = ({props}) => {
  const visualDuration = videoTimelineDurationSeconds(props.cuts);
  const endCard = props.profiles.branding.end_card;
  const endCardDuration = endCard?.enabled ? endCard.duration_seconds : 0;
  const durationSeconds = Math.max(1, visualDuration + endCardDuration);
  const fps = props.profiles.export.fps ?? 30;
  return {
    durationInFrames: Math.ceil(durationSeconds * fps),
    fps,
    width: props.profiles.export.width,
    height: props.profiles.export.height,
  };
};
