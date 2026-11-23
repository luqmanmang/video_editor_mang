import { MyComposition } from "./Composition";
import { KautharMinimalV3 } from "./KautharMinimalV3";
import { KautharMinimalV31 } from "./KautharMinimalV31";
import { Semantic720 } from "./Semantic720";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <MyComposition />
      <KautharMinimalV3 />
      <KautharMinimalV31 />
      <Semantic720 />
    </>
  );
};
