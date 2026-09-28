type Props = {
  name: string;
  meta: string;
  selected?: boolean;
  onClick: () => void;
};

export default function FolderTile({ name, meta, selected, onClick }: Props) {
  return (
    <button
      type="button"
      className={selected ? "sa-folder-tile on" : "sa-folder-tile"}
      onClick={onClick}
      aria-pressed={selected}
    >
      <span className="sa-folder-icon" aria-hidden>
        <svg viewBox="0 0 48 40" width="36" height="30">
          <path
            d="M2 10.5c0-1.9 1.5-3.5 3.4-3.5H16l3.2 3.2H42.6c1.9 0 3.4 1.6 3.4 3.5V34c0 1.9-1.5 3.5-3.4 3.5H5.4C3.5 37.5 2 35.9 2 34V10.5Z"
            fill="currentColor"
            opacity="0.22"
          />
          <path
            d="M2 14.2c0-1.7 1.4-3.1 3.1-3.1h37.8c1.7 0 3.1 1.4 3.1 3.1V33c0 1.7-1.4 3.1-3.1 3.1H5.1C3.4 36.1 2 34.7 2 33V14.2Z"
            fill="currentColor"
            opacity="0.55"
          />
        </svg>
      </span>
      <span className="sa-folder-name">{name}</span>
      <span className="sa-folder-meta">{meta}</span>
    </button>
  );
}
