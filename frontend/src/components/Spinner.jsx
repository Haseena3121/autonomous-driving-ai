export default function Spinner({ label = 'Loading…', small = false }) {
  return (
    <div className={small ? 'spinner-wrap spinner-small' : 'spinner-wrap'}>
      <span className="spinner" aria-hidden="true" />
      <span className="spinner-label">{label}</span>
    </div>
  );
}
