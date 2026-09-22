export function PageSkeleton({ cards = 3 }: { cards?: number }) {
  return (
    <section className="page-skeleton" aria-label="Đang tải nội dung" aria-busy="true">
      <div className="skeleton-line skeleton-kicker" />
      <div className="skeleton-line skeleton-title" />
      <div className="skeleton-line skeleton-copy" />
      <div className="skeleton-grid">
        {Array.from({ length: cards }, (_, index) => (
          <div className="skeleton-card" key={index}>
            <div className="skeleton-line skeleton-card-title" />
            <div className="skeleton-line" />
            <div className="skeleton-line skeleton-short" />
          </div>
        ))}
      </div>
      <span className="sr-only">Đang tải…</span>
    </section>
  );
}
