type Tab = { id: string; label: string };

type Props = {
  tabs: Tab[];
  active: string;
  onSelect: (id: string) => void;
};

export default function DatabaseTabs({ tabs, active, onSelect }: Props) {
  return (
    <nav className="ju-wh-tabs">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className={tab.id === active ? "is-active" : undefined}
          onClick={() => onSelect(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
}
