export default function ProgressBar({ value = 0, indeterminate = false, label }) {
  const pct = indeterminate ? 100 : Math.min(100, Math.max(0, value));
  return (
    <div className="progress-wrap">
      <div
        className={`progress ${indeterminate ? 'progress-indeterminate' : ''}`}
        role="progressbar"
        aria-valuenow={indeterminate ? undefined : Math.round(pct)}
      >
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
      {label ? <span className="progress-label">{label}</span> : null}
    </div>
  );
}
