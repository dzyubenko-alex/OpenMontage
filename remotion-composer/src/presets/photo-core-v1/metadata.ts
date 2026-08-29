import type {CalculateMetadataFunction} from "remotion";
import type {PhotoCoreV1Props} from "./types";

export const calculatePhotoCoreV1Metadata: CalculateMetadataFunction<PhotoCoreV1Props> = ({props}) => {
  const visualEnd = props.cuts.reduce((max, cut) => Math.max(max, cut.out_seconds), 0);
  const endCard = props.profiles.branding.end_card;
  const endCardDuration = endCard?.enabled ? endCard.duration_seconds : 0;
  const durationSeconds = Math.max(1, visualEnd + endCardDuration);

  const exportProfile = props.profiles.export;
  const fps = exportProfile.fps ?? 30;

  return {
    durationInFrames: Math.ceil(durationSeconds * fps),
    fps,
    width: exportProfile.width,
    height: exportProfile.height,
  };
};
