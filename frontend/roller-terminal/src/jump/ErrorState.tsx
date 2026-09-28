type Props = { message: string };

export default function ErrorState({ message }: Props) {
  return (
    <div className="ju-drive-error" role="alert">
      <p>{message}</p>
    </div>
  );
}
