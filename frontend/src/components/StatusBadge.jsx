const META = {
  loaded: { tone: 'green', label: 'Loaded' },
  ok: { tone: 'green', label: 'Operational' },
  completed: { tone: 'green', label: 'Completed' },
  connected: { tone: 'green', label: 'Connected' },
  available: { tone: 'green', label: 'Available' },
  trained_by_me: { tone: 'green', label: 'Trained by me' },
  processing: { tone: 'blue', label: 'Processing' },
  loading: { tone: 'blue', label: 'Loading' },
  queued: { tone: 'blue', label: 'Queued' },
  standby: { tone: 'blue', label: 'Ready' },
  not_loaded: { tone: 'gray', label: 'Ready' },
  none: { tone: 'gray', label: 'None' },
  missing: { tone: 'blue', label: 'Ready' },
  error: { tone: 'red', label: 'Error' },
  failed: { tone: 'red', label: 'Failed' },
  unavailable: { tone: 'red', label: 'Unavailable' },
};

export default function StatusBadge({ status, label }) {
  const meta = META[status] || { tone: 'gray', label: status || 'Unknown' };
  return <span className={`badge badge-${meta.tone}`}>{label || meta.label}</span>;
}
