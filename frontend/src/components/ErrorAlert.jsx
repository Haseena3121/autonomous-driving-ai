/**
 * Error banner. If the ApiError carries backend `details.instructions`
 * (e.g. model missing, CARLA offline), they are rendered as a checklist.
 */
export default function ErrorAlert({ error, title = 'Something went wrong', onRetry }) {
  if (!error) return null;
  const message = typeof error === 'string' ? error : error.message;
  const instructions = typeof error === 'object' ? error.details?.instructions : null;
  return (
    <div className="alert alert-error" role="alert">
      <div className="alert-head">
        <strong>{title}</strong>
        {onRetry ? (
          <button type="button" className="btn btn-ghost btn-sm" onClick={onRetry}>
            Retry
          </button>
        ) : null}
      </div>
      <p>{message}</p>
      {Array.isArray(instructions) && instructions.length > 0 ? (
        <ul className="alert-list">
          {instructions.map((line, index) => (
            <li key={index}>{line}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
