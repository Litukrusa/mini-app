import { weekDays } from "../utils/dates";

export function WeekStrip({ selectedDate, onSelect }) {
  const days = weekDays(parseIsoSafe(selectedDate));

  return (
    <div className="week-strip">
      {days.map((d) => {
        const active = d.iso === selectedDate;
        return (
          <button
            key={d.iso}
            type="button"
            className={`week-day${active ? " week-day--active" : ""}`}
            onClick={() => onSelect(d.iso)}
          >
            <span className="week-day__dow">{d.dow}</span>
            <span className="week-day__num">{d.day}</span>
            <span className="week-day__mon">{d.month}</span>
          </button>
        );
      })}
    </div>
  );
}

function parseIsoSafe(iso) {
  const [y, m, d] = (iso || "").split("-").map(Number);
  if (!y) return new Date();
  return new Date(y, m - 1, d);
}
