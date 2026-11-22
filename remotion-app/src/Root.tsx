import { MyComposition } from "./Composition";
import { KautharMinimalV3 } from "./KautharMinimalV3";
import { KautharMinimalV31 } from "./KautharMinimalV31";
import { Semantic720 } from "./Semantic720";
import {KautharHeadlineA720, KautharHeadlineB720} from "./KautharHeadlineAB720";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <MyComposition />
      <KautharMinimalV3 />
      <KautharMinimalV31 />
      <Semantic720 />
      <KautharHeadlineA720 />
      <KautharHeadlineB720 />
    </>
  );
};
