import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { absoluteUrl, api } from '../services/api.js';
import DetectionTable from '../components/DetectionTable.jsx';
import Dropzone from '../components/Dropzone.jsx';
import ErrorAlert from '../components/ErrorAlert.jsx';
import ImageResult from '../components/ImageResult.jsx';
import PageHeader from '../components/PageHeader.jsx';
import Spinner from '../components/Spinner.jsx';
import StatCard from '../components/StatCard.jsx';

const ACCEPT = 'image/png,image/jpeg,image/bmp,image/webp';

export default function ObjectDetection() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [conf, setConf] = useState(0.25);
  const [iou, setIou] = useState(0.45);
  const [imgsz, setImgsz] = useState(640);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!file) {
      setPreview(null);
      return undefined;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const run = async () => {
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const data = await api.detectImage(file, { conf, iou, imgsz });
      setResult(data);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Object Detection"
        description="The uploaded image is sent to the Flask API and inferred with YOUR trained best.pt — every box, label and score below comes from the real model."
      />

      <div className="card pad">
        <Dropzone
          file={file}
          onFile={setFile}
          accept={ACCEPT}
          label="Drop an image here or click to browse"
          hint="PNG · JPG · BMP · WEBP — up to 16 MB (a road scene works best)"
        />

        <div className="controls">
          <label className="field">
            <span>Confidence threshold: <strong>{conf.toFixed(2)}</strong></span>
            <input type="range" min="0.05" max="0.95" step="0.05" value={conf} onChange={(e) => setConf(Number(e.target.value))} />
          </label>
          <label className="field">
            <span>IoU (NMS): <strong>{iou.toFixed(2)}</strong></span>
            <input type="range" min="0.1" max="0.9" step="0.05" value={iou} onChange={(e) => setIou(Number(e.target.value))} />
          </label>
          <label className="field">
            <span>Inference size</span>
            <select value={imgsz} onChange={(e) => setImgsz(Number(e.target.value))}>
              {[320, 480, 640, 960, 1280].map((v) => (
                <option key={v} value={v}>{v} px</option>
              ))}
            </select>
          </label>
          <button type="button" className="btn btn-primary" disabled={!file || busy} onClick={run}>
            {busy ? 'Running inference…' : '▶ Run detection'}
          </button>
        </div>
      </div>

      {busy ? <Spinner label="Running YOLO inference on the server…" /> : null}
      <ErrorAlert error={error} onRetry={file ? run : undefined} />
      {error && error.code === 'MODEL_NOT_LOADED' ? (
        <div className="alert alert-warn">
          See <Link to="/model-info">Model Information</Link> for the exact expected weights path and the{' '}
          <Link to="/documentation">Documentation</Link> page for the Colab training workflow.
        </div>
      ) : null}

      {result ? (
        <>
          <div className="grid grid-4">
            <StatCard label="Total detections" value={result.total} accent />
            <StatCard label="Inference time" value={`${result.inference_ms} ms`} sub={`device: ${String(result.device || 'cpu').toUpperCase()}`} />
            <StatCard label="Classes found" value={result.stats.class_count} sub={Object.keys(result.stats.per_class).slice(0, 3).join(', ')} />
            <StatCard label="Avg confidence" value={result.stats.avg_confidence != null ? `${(result.stats.avg_confidence * 100).toFixed(1)}%` : '—'} />
          </div>

          <section className="section">
            <h2>Result viewer</h2>
            <ImageResult
              originalSrc={preview}
              resultSrc={result.annotated_image}
              originalLabel="Original image"
              resultLabel={`Annotated — ${result.total} object(s)`}
              downloadUrl={absoluteUrl(result.annotated_url)}
              downloadName="adas-annotated.jpg"
            />
          </section>

          <section className="section">
            <h2>Detected objects</h2>
            <div className="card">
              <DetectionTable detections={result.detections} />
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
