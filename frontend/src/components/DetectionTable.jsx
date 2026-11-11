import EmptyState from './EmptyState.jsx';

/** Table of real detections produced by the trained model. */
export default function DetectionTable({ detections, showTrackId = false }) {
  if (!detections || detections.length === 0) {
    return <EmptyState icon="◻" title="No objects detected" text="The model found no objects above the confidence threshold in this frame." />;
  }
  const maxConf = Math.max(...detections.map((d) => d.confidence), 1);
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>#</th>
            <th>Class</th>
            <th>Confidence</th>
            {showTrackId ? <th>Track ID</th> : null}
            <th>Bounding box (x1, y1, x2, y2)</th>
          </tr>
        </thead>
        <tbody>
          {detections.map((det, index) => (
            <tr key={`${det.track_id ?? 'd'}-${index}`}>
              <td>{index + 1}</td>
              <td><span className="chip">{det.class_name}</span></td>
              <td>
                <div className="conf-cell">
                  <span className="conf-bar" style={{ width: `${(det.confidence / maxConf) * 100}%` }} />
                  <span className="conf-value">{(det.confidence * 100).toFixed(1)}%</span>
                </div>
              </td>
              {showTrackId ? <td>{det.track_id != null ? `#${det.track_id}` : '—'}</td> : null}
              <td className="mono">
                {det.bbox.map((v) => Math.round(v)).join(', ')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
