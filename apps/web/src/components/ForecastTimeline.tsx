import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { componentLabel, formatPercent, formatWindow, signalLabel } from "../lib/format";
import type { ForecastWindow } from "../lib/types";

interface Props {
  windows: ForecastWindow[];
}

interface ChartRow {
  label: string;
  probability: number;
  index: number;
}

interface DirectLabelProps {
  x?: number;
  y?: number;
  width?: number;
  value?: number;
  index?: number;
}

/**
 * One direct label, on the selected bar only.
 *
 * A value above every column is noise and goes unread; the axis carries the
 * rest and the tooltip carries the detail.
 */
function SelectedLabel({ x, y, width, value, index, selected }: DirectLabelProps & {
  selected: number;
}) {
  if (index !== selected || x === undefined || y === undefined || width === undefined) {
    return null;
  }
  return (
    <text
      x={x + width / 2}
      y={y - 8}
      textAnchor="middle"
      fill="var(--text)"
      fontSize={13}
      fontWeight={700}
    >
      {value}%
    </text>
  );
}

/**
 * Upcoming opportunities, ranked.
 *
 * Selecting a bar opens the breakdown behind that specific window, so a number
 * is never presented without its reasoning.
 */
export function ForecastTimeline({ windows }: Props) {
  const [selectedIndex, setSelectedIndex] = useState(0);

  if (windows.length === 0) {
    return <p className="empty-note">No scored windows in the forecast horizon.</p>;
  }

  const rows: ChartRow[] = windows.map((window, index) => ({
    label: formatWindow(window),
    probability: Math.round(window.probability * 100),
    index,
  }));

  const selected = windows[Math.min(selectedIndex, windows.length - 1)];

  // Bars encode magnitude by length, so the baseline stays at zero - but a
  // fixed 0-100 ceiling squashes a forecast that never exceeds 25%. The top
  // rounds up to a clean number above the data instead.
  const peak = Math.max(...rows.map((row) => row.probability));
  const axisMax = Math.min(100, Math.max(20, Math.ceil((peak + 8) / 10) * 10));
  const step = axisMax <= 40 ? 10 : 25;
  const ticks = Array.from({ length: Math.floor(axisMax / step) + 1 }, (_, i) => i * step);

  return (
    <div className="timeline">
      <div className="timeline__chart">
        <ResponsiveContainer width="100%" height={260}>
          <BarChart
            data={rows}
            margin={{ top: 22, right: 8, bottom: 8, left: 8 }}
            barCategoryGap="22%"
          >
            <CartesianGrid strokeDasharray="2 4" stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 12, fill: "var(--text-muted)" }}
              interval={0}
              angle={-25}
              textAnchor="end"
              height={64}
              axisLine={{ stroke: "var(--border)" }}
              tickLine={false}
            />
            <YAxis
              domain={[0, axisMax]}
              ticks={ticks}
              tickFormatter={(value: number) => `${value}%`}
              tick={{ fontSize: 12, fill: "var(--text-muted)" }}
              width={44}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              cursor={{ fill: "var(--surface-hover)" }}
              formatter={(value: number) => [`${value}%`, "Forecast score"]}
              contentStyle={{
                background: "var(--surface)",
                border: "1px solid var(--border-strong)",
                borderRadius: 9,
                color: "var(--text)",
                boxShadow: "var(--shadow)",
              }}
              labelStyle={{ color: "var(--text-muted)", fontSize: 12 }}
            />
            <Bar
              dataKey="probability"
              radius={[4, 4, 0, 0]}
              onClick={(_entry: unknown, index: number) => setSelectedIndex(index)}
              cursor="pointer"
              isAnimationActive={false}
            >
              {rows.map((row) => (
                <Cell
                  key={row.index}
                  fill={
                    row.index === selectedIndex ? "var(--accent)" : "var(--accent-soft)"
                  }
                />
              ))}
              <LabelList
                dataKey="probability"
                content={(props) => (
                  <SelectedLabel {...(props as DirectLabelProps)} selected={selectedIndex} />
                )}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="timeline__list" role="list">
        {windows.map((window, index) => (
          <button
            key={window.windowStart}
            type="button"
            role="listitem"
            className={`timeline__item ${index === selectedIndex ? "timeline__item--active" : ""}`}
            onClick={() => setSelectedIndex(index)}
            aria-pressed={index === selectedIndex}
          >
            <span>{formatWindow(window)}</span>
            <strong>{formatPercent(window.probability)}</strong>
          </button>
        ))}
      </div>

      {selected && <WindowBreakdown window={selected} />}
    </div>
  );
}

function WindowBreakdown({ window }: { window: ForecastWindow }) {
  const signals = window.explanation?.signals ?? {};

  return (
    <section className="card breakdown">
      <h4 className="breakdown__title">Why this prediction?</h4>

      {Object.keys(signals).length > 0 && (
        <dl className="breakdown__signals">
          {Object.entries(signals).map(([key, value]) => (
            <div key={key} className="breakdown__signal">
              <dt>{signalLabel(key)}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}

      <h5 className="breakdown__subtitle">Score components</h5>
      <ul className="breakdown__components">
        {Object.entries(window.components).map(([key, value]) => (
          <li key={key}>
            <span>{componentLabel(key)}</span>
            <span className="breakdown__bar" aria-hidden="true">
              <span className="breakdown__bar-fill" style={{ width: `${value * 100}%` }} />
            </span>
            <span className="breakdown__value">{value.toFixed(2)}</span>
          </li>
        ))}
      </ul>

      <p className="breakdown__scales">
        Weighted score {window.rawScore.toFixed(3)}, scaled by sample size&nbsp;
        {window.sampleScale.toFixed(2)} and source confidence {window.sourceScale.toFixed(2)}.
      </p>

      {window.explanation?.reasons?.length ? (
        <ul className="breakdown__reasons">
          {window.explanation.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
