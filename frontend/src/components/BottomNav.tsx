export type TabKey = "voice" | "schemes" | "status" | "grievance";

interface BottomNavProps {
  active: TabKey;
  onChange: (tab: TabKey) => void;
  badge?: number;
}

const ITEMS: { key: TabKey; label: string; icon: string }[] = [
  { key: "voice", label: "बोलें", icon: "🎙️" },
  { key: "schemes", label: "योजनाएँ", icon: "📋" },
  { key: "status", label: "स्थिति", icon: "🔎" },
  { key: "grievance", label: "शिकायत", icon: "📣" },
];

export default function BottomNav({ active, onChange, badge = 0 }: BottomNavProps) {
  return (
    <nav
      aria-label="मुख्य मेन्यू"
      className="safe-bottom border-t border-ink-200 bg-white/95 backdrop-blur"
    >
      <ul className="mx-auto flex max-w-md items-stretch">
        {ITEMS.map((item) => {
          const isActive = active === item.key;
          return (
            <li key={item.key} className="flex-1">
              <button
                type="button"
                onClick={() => onChange(item.key)}
                aria-current={isActive ? "page" : undefined}
                className={`relative flex w-full flex-col items-center gap-0.5 px-1 py-2.5 transition-colors ${
                  isActive ? "text-brand-700" : "text-ink-500 hover:text-ink-700"
                }`}
              >
                <span aria-hidden="true" className="text-xl leading-none">
                  {item.icon}
                </span>
                <span className="text-[11px] font-semibold">{item.label}</span>
                {isActive && (
                  <span
                    aria-hidden="true"
                    className="absolute inset-x-4 top-0 h-[3px] rounded-b-full bg-brand-600"
                  />
                )}
                {item.key === "grievance" && badge > 0 && (
                  <span className="absolute right-3 top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-alert-600 px-1 text-[10px] font-bold text-white">
                    {badge}
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
