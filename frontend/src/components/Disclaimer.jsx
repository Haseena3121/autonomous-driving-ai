/** Highlighted caveat box (e.g. "relative depth is not metric distance"). */
export default function Disclaimer({ tone = 'warn', title, children }) {
  return (
    <div className={`alert alert-${tone}`}>
      {title ? <strong>{title}</strong> : null}
      <p style={{ margin: 0 }}>{children}</p>
    </div>
  );
}
