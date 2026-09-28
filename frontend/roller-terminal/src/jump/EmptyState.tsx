type Props = { message: string };

export default function EmptyState({ message }: Props) {
  return (
    <div className="ju-drive-empty">
      <p>{message}</p>
    </div>
  );
}
