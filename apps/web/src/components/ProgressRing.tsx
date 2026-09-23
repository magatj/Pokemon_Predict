interface Props {
  /** 0..1 */
  value: number;
  label: string;
  /** Muted styling for a network-level figure, which is not machine-specific. */
  muted?: boolean;
  size?: number;
}

/**
 * The headline probability, as a ring.
 *
 * The ring is decorative reinforcement - the number inside carries the value,
 * so the figure is never conveyed by the arc alone.
 */
export function ProgressRing({ value, label, muted = false, size = 132 }: Props) {
  const clamped = Math.min(Math.max(value, 0), 1);
  const stroke = 11;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped);
  const percent = Math.round(clamped * 100);

  return (
    <div className="ring" style={{ width: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--ring-track)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={muted ? "var(--accent)" : "var(--good)"}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="ring__value">
        <span className={`ring__number ${muted ? "ring__number--muted" : ""}`}>{percent}</span>
        <span className="ring__unit">%</span>
      </div>
      <span className="ring__label">{label}</span>
    </div>
  );
}
