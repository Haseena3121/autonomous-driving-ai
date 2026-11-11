import { useEffect, useRef, useState } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { absoluteUrl, api } from '../services/api.js';
import Dropzone from '../components/Dropzone.jsx';
import ErrorAlert from '../components/ErrorAlert.jsx';
import PageHeader from '../components/PageHeader.jsx';
import ProgressBar from '../components/ProgressBar.jsx';
import Spinner from '../components/Spinner.jsx';
import StatCard from '../components/StatCard.jsx';
import StatusBadge from '../components/StatusBadge.jsx';

const ACCEPT = 'video/mp4,video/quicktime,video/x-msvideo,video/x-matroska,.mp4,.avi,.mov,.mkv';

export default function VideoAnalysis() {
  const [file, setFile] = useState(null);
  const [conf, setConf] = useState(0.25);
  const [iou, setIou] = useState(0.45);
  const [imgsz, setImgsz] = useState(640);
  const [uploadPct, setUploadPct] = useState(null);
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);

  useEffect(() => () => clearInterval(pollRef.current), []);

  const start = async () => {
    if (!file || uploadPct != null) return;
    setError(null);
    setJob(null);
    clearInterval(pollRef.current);
    try {
      const created = await api.startVideoJob('detect', file, { conf, iou, imgsz }, setUploadPct);
      setJob(created);
      pollRef.current = setInterval(async () => {
        try {
          const updated = await api.getJob(created.job_id);
          setJob(updated);
          if (updated.status === 'completed' || updated.status === 'failed') {
            clearInterval(pollRef.current);
          }
        } catch (err) {
          setError(err);
          clearInterval(pollRef.current);
        }
      }, 1500);
    } catch (err) {
      setError(err);
    } finally {
      setUploadPct(null);
    }
  };

  const processing = job && (job.status === 'queued' || job.status === 'processing');
  const classData = job?.stats?.per_class
    ? Object.entries(job.stats.per_class).map(([name, count]) => ({ name, count }))
    : [];

  return (
    <div>
      <PageHeader
        title="Video Analysis"
        description="Videos are processed frame by frame on the server (never loaded into memory at once). Every detection comes from your trained model; progress is polled live from the job API."
      />

      <div className="card pad">
        <Dropzone
          file={file}
          onFile={(f) => {
            setFile(f);
            setJob(null);
            setError(null);
          }}
          accept={ACCEPT}
          label="Drop a video here or click to browse"
          hint="MP4 · AVI · MOV · MKV — up to 200 MB"
        />
        <div className="controls">
          <label className="field">
            <span>Confidence: <strong>{conf.toFixed(2)}</strong></span>
            <input type="range" min="0.05" max="0.95" step="0.05" value={conf} onChange={(e) => setConf(Number(e.target.value))} />
          </label>
          <label className="field">
            <span>IoU: <strong>{iou.toFixed(2)}</strong></span>
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
          <button type="button" className="btn btn-primary" disabled={!file || uploadPct != null} onClick={start}>
            ⚙ Process video
          </button>
        </div>
      </div>

      {uploadPct != null ? (
        <div className="card pad">
          <ProgressBar value={uploadPct} label={`Uploading… ${uploadPct}%`} />
        </div>
      ) : null}

      <ErrorAlert error={error} onRetry={file ? start : undefined} />

      {processing ? (
        <div className="card pad">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <StatusBadge status={job.status} />
            <span className="muted">
              frame {job.frames_processed}
              {job.total_frames ? ` / ${job.total_frames}` : ''} · job <span className="mono">{job.job_id}</span>
            </span>
          </div>
          <ProgressBar
            value={job.progress ?? 0}
            indeterminate={job.progress == null}
            label={job.progress != null ? `Processing… ${job.progress}%` : 'Processing… (counting frames)'}
          />
        </div>
      ) : null}

      {job?.status === 'failed' ? (
        <ErrorAlert error={{ message: job.error || 'The video job failed on the server.', details: null }} title="Processing failed" />
      ) : null}

      {job?.status === 'completed' ? (
        <>
          <div className="grid grid-4">
            <StatCard label="Frames processed" value={job.frames_processed} accent />
            <StatCard label="Avg inference / frame" value={`${job.stats.avg_inference_ms} ms`} />
            <StatCard label="Processing speed" value={job.stats.processing_fps ? `${job.stats.processing_fps} FPS` : '—'} sub={`video: ${job.stats.video_fps} FPS`} />
            <StatCard label="Resolution" value={`${job.stats.width}×${job.stats.height}`} />
          </div>

          <section className="section">
            <h2>Annotated output</h2>
            <div className="card pad video-card">
              <video controls src={absoluteUrl(job.output.url)} preload="metadata" />
              <div className="row">
                <a className="btn btn-primary" href={`${absoluteUrl(job.output.url)}?download=1`}>
                  ⬇ Download annotated video
                </a>
                <span className="muted">
                  If the preview does not play in your browser, use the download button — playback depends on the
                  H.264 encoder being available (the backend re-encodes with ffmpeg when installed).
                </span>
              </div>
            </div>
          </section>

          {classData.length > 0 ? (
            <section className="section">
              <h2>Detections per class (all frames combined)</h2>
              <div className="card pad">
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={classData} margin={{ top: 8, right: 16, left: -12, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1d2a45" />
                    <XAxis dataKey="name" stroke="#8b98ad" tick={{ fontSize: 12 }} interval={0} angle={-18} dy={8} />
                    <YAxis stroke="#8b98ad" tick={{ fontSize: 12 }} allowDecimals={false} />
                    <Tooltip contentStyle={{ background: '#0d1526', border: '1px solid #1d2a45', borderRadius: 8, color: '#e7eef9' }} />
                    <Bar dataKey="count" fill="#3b82f6" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>
          ) : (
            <div className="alert alert-warn">
              The model found no objects above the confidence threshold in this video.
            </div>
          )}
        </>
      ) : null}

      {job == null && uploadPct == null ? (
        <div className="card pad muted">
          Upload a video and press <strong>Process video</strong>. The job runs in a background thread — you can
          watch live progress here; the annotated result and download appear when it completes.
        </div>
      ) : null}
    </div>
  );
}
