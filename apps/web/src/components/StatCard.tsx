interface Props {
  icon: JSX.Element;
  title: string;
  value: string;
  /** Colour cue for the value; always paired with the text, never alone. */
  tone?: "default" | "good" | "bad" | "warn" | "muted";
  detail?: React.ReactNode;
  /** A small leading dot, e.g. an online indicator. */
  dot?: boolean;
}

export function StatCard({ icon, title, value, tone = "default", detail, dot }: Props) {
  return (
    <article className="stat-card">
      <h3 className="stat-card__title">{title}</h3>
      <div className="stat-card__body">
        <span className="stat-card__icon" aria-hidden="true">
          {icon}
        </span>
        <div>
          <p className={`stat-card__value stat-card__value--${tone}`}>
            {dot && <span className={`dot dot--${tone}`} aria-hidden="true" />}
            {value}
          </p>
          {detail && <p className="stat-card__detail">{detail}</p>}
        </div>
      </div>
    </article>
  );
}
