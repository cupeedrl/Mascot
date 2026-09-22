import { ChevronLeft, ChevronRight, Flame } from "lucide-react";

interface CalendarDay {
  isoDate: string;
  dayNumber: number;
  isCurrentMonth: boolean;
}

interface StudyActivityCalendarProps {
  year: number;
  month: number;
  today: string;
  activeDates: string[];
  currentStreak: number;
  longestStreak: number;
  isLoading?: boolean;
  error?: string | null;
  onPreviousMonth: () => void;
  onNextMonth: () => void;
}

const weekdayLabels = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"];

function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function buildCalendarDays(year: number, month: number): CalendarDay[] {
  const firstDay = new Date(Date.UTC(year, month - 1, 1));
  const mondayOffset = (firstDay.getUTCDay() + 6) % 7;
  const calendarStart = new Date(firstDay);
  calendarStart.setUTCDate(firstDay.getUTCDate() - mondayOffset);

  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(calendarStart);
    date.setUTCDate(calendarStart.getUTCDate() + index);
    return {
      isoDate: isoDate(date),
      dayNumber: date.getUTCDate(),
      isCurrentMonth: date.getUTCMonth() === month - 1,
    };
  });
}

export function StudyActivityCalendar({
  year,
  month,
  today,
  activeDates,
  currentStreak,
  longestStreak,
  isLoading = false,
  error,
  onPreviousMonth,
  onNextMonth,
}: StudyActivityCalendarProps) {
  const days = buildCalendarDays(year, month);
  const active = new Set(activeDates);
  const monthLabel = new Intl.DateTimeFormat("vi-VN", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year, month - 1, 1)));

  return (
    <section className={`study-calendar-card${isLoading ? " loading" : ""}`} aria-label="Lịch hoạt động học tập">
      <header className="study-calendar-header">
        <div>
          <span className="study-calendar-eyebrow">Hoạt động học tập</span>
          <strong>{monthLabel.charAt(0).toUpperCase() + monthLabel.slice(1)}</strong>
        </div>
        <div className="study-calendar-navigation">
          <button type="button" aria-label="Tháng trước" onClick={onPreviousMonth}>
            <ChevronLeft size={15} />
          </button>
          <button type="button" aria-label="Tháng sau" onClick={onNextMonth}>
            <ChevronRight size={15} />
          </button>
        </div>
      </header>

      <div className="study-calendar-streaks">
        <span><Flame size={14} /><b>{currentStreak}</b> ngày hiện tại</span>
        <span>Kỷ lục <b>{longestStreak}</b> ngày</span>
      </div>

      <div className="study-calendar-body">
        <div className="study-calendar-weekdays" aria-hidden="true">
          {weekdayLabels.map((label) => <span key={label}>{label}</span>)}
        </div>
        <div className="study-calendar-grid" aria-label={monthLabel}>
          {days.map((day) => {
            const isActive = active.has(day.isoDate);
            const isToday = day.isoDate === today;
            const classNames = [
              !day.isCurrentMonth ? "outside" : "",
              isActive ? "active" : "",
              isToday ? "today" : "",
            ].filter(Boolean).join(" ");
            return (
              <time
                key={day.isoDate}
                dateTime={day.isoDate}
                className={classNames}
                aria-label={`${day.isoDate}${isActive ? ", có hoạt động học" : ""}${isToday ? ", hôm nay" : ""}`}
              >
                {day.dayNumber}
              </time>
            );
          })}
        </div>
      </div>
      <footer className="study-calendar-legend">
        {error ? (
          <span className="study-calendar-error" role="status">{error}</span>
        ) : (
          <>
            <span><i className="active" />Đã học</span>
            <span><i className="today" />Hôm nay</span>
          </>
        )}
      </footer>
    </section>
  );
}
