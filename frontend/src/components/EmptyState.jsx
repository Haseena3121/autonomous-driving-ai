export default function EmptyState({ icon = '◎', title, text }) {
  return (
    <div className="empty-state">
      <div className="empty-icon" aria-hidden="true">{icon}</div>
      <h3>{title}</h3>
      {text ? <p>{text}</p> : null}
    </div>
  );
}
