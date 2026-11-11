/**
 * Metric card for performance numbers. `available=false` renders the honest
 * "Not available" state instead of inventing a value.
 */
export default function MetricCard({ label, value, sub, available = true, accent = false }) {
  return (
    <div className={`card stat-card ${accent ? 'stat-accent' : ''}`}>
      <div className="stat-label">{label}</div>
      {available ? (
        <>
          <div className="stat-value">{value}</div>
          {sub ? <div className="stat-sub">{sub}</div> : null}
        </>
      ) : (
        <div className="stat-value stat-na">Not available</div>
      )}
    </div>
  );
}
