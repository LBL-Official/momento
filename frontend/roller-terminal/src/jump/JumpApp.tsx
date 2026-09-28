import JumpShell from "./JumpShell";

type Props = {
  onBackToSuperASI: () => void;
  onBackToRoller: () => void;
};

export default function JumpApp({ onBackToSuperASI, onBackToRoller }: Props) {
  return <JumpShell onBackToSuperASI={onBackToSuperASI} onBackToRoller={onBackToRoller} />;
}
