export default function StatCard({ label, value, sub, tone = 'default' }) {
  return (
    <div className={`card stat-card stat-${tone}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub ? <div className="stat-sub">{sub}</div> : null}
    </div>
  );
}
