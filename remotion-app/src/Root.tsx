import { MyComposition } from "./Composition";
import { KautharMinimalV3 } from "./KautharMinimalV3";
import { KautharMinimalV31 } from "./KautharMinimalV31";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <MyComposition />
      <KautharMinimalV3 />
      <KautharMinimalV31 />
    </>
  );
};
