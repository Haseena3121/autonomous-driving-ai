import { useState } from 'react';
import { api } from '../services/api.js';
import Disclaimer from '../components/Disclaimer.jsx';
import Dropzone from '../components/Dropzone.jsx';
import ErrorAlert from '../components/ErrorAlert.jsx';
import ImageResult from '../components/ImageResult.jsx';
import PageHeader from '../components/PageHeader.jsx';
import Spinner from '../components/Spinner.jsx';
import StatCard from '../components/StatCard.jsx';
import StatusBadge from '../components/StatusBadge.jsx';

const ACCEPT = 'image/png,image/jpeg,image/bmp,image/webp';

export default function DepthEstimation() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [withObjects, setWithObjects] = useState(true);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const run = async () => {
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const data = await api.depthEstimate(file, { withObjects });
      setResult(data);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const objects = result?.objects || [];
  const maxDepth = objects.length ? Math.max(...objects.map((o) => o.relative_depth)) : 1;

  return (
    <div>
      <PageHeader
        title="Depth Estimation"
        description="MiDaS monocular depth estimation runs on the uploaded image. Object-level read-outs combine the depth map with detections from your trained YOLO model."
      />

      <Disclaimer tone="warn" title="Relative depth — not metric distance">
        MiDaS estimates <strong>relative (inverse) depth</strong>. Values are normalised scores where higher = closer
        to the camera. They are <strong>not exact distances in metres</strong>.
      </Disclaimer>

      <div className="card pad" style={{ marginTop: 16 }}>
        <Dropzone
          file={file}
          onFile={(f) => {
            setFile(f);
            setPreview(f ? URL.createObjectURL(f) : null);
            setResult(null);
          }}
          accept={ACCEPT}
          label="Drop an image here or click to browse"
          hint="First run downloads the MiDaS weights (~70 MB) into backend/models/midas_cache/"
        />
        <div className="controls">
          <label className="field field-check">
            <input type="checkbox" checked={withObjects} onChange={(e) => setWithObjects(e.target.checked)} />
            <span>Combine with YOLO detections (object-level depth)</span>
          </label>
          <button type="button" className="btn btn-primary" disabled={!file || busy} onClick={run}>
            {busy ? 'Estimating…' : '▶ Estimate depth'}
          </button>
        </div>
      </div>

      {busy ? <Spinner label="Running MiDaS (first run downloads weights)…" /> : null}
      <ErrorAlert error={error} onRetry={file ? run : undefined} />

      {result ? (
        <>
          <div className="grid grid-4">
            <StatCard label="MiDaS model" value={result.status.model_type} accent />
            <StatCard label="Device" value={String(result.status.device || 'cpu').toUpperCase()} />
            <StatCard label="Inference time" value={`${result.inference_ms} ms`} />
            <StatCard label="Depth range (norm.)" value={`${result.depth_range.min} – ${result.depth_range.max}`} />
          </div>

          <section className="section">
            <h2>Depth map</h2>
            <ImageResult
              originalSrc={preview}
              resultSrc={result.depth_image}
              originalLabel="Input image"
              resultLabel="Relative depth (bright = close)"
            />
          </section>

          {result.detection_note ? (
            <div className="alert alert-info">{result.detection_note}</div>
          ) : null}

          <section className="section">
            <h2>Object-level depth</h2>
            <div className="card">
              {objects.length === 0 ? (
                <p className="pad muted" style={{ margin: 0 }}>
                  No objects to score — either the YOLO model is not loaded or nothing was detected in this image.
                </p>
              ) : (
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Class</th>
                        <th>Confidence</th>
                        <th>Relative depth (higher = closer)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {objects.map((obj, index) => (
                        <tr key={`${obj.class_name}-${index}`}>
                          <td><span className="chip">{obj.class_name}</span>{obj.track_id != null ? ` #${obj.track_id}` : ''}</td>
                          <td>{(obj.confidence * 100).toFixed(1)}%</td>
                          <td>
                            <div className="conf-cell">
                              <span className="conf-bar conf-bar-depth" style={{ width: `${(obj.relative_depth / maxDepth) * 100}%` }} />
                              <span className="conf-value">{obj.relative_depth.toFixed(3)}</span>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </section>

          <div className="card pad">
            <div className="kv-grid">
              <div className="kv"><span>Status</span><StatusBadge status={result.status.available ? 'available' : 'unavailable'} label={result.status.message.split('.')[0]} /></div>
              <div className="kv"><span>Disclaimer</span><strong style={{ maxWidth: 480 }}>{result.disclaimer}</strong></div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
