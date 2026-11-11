import { useEffect, useRef, useState } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { absoluteUrl, api } from '../services/api.js';
import Dropzone from '../components/Dropzone.jsx';
import ErrorAlert from '../components/ErrorAlert.jsx';
import PageHeader from '../components/PageHeader.jsx';
import ProgressBar from '../components/ProgressBar.jsx';
import StatCard from '../components/StatCard.jsx';
import StatusBadge from '../components/StatusBadge.jsx';

const ACCEPT = 'video/mp4,video/quicktime,video/x-msvideo,video/x-matroska,.mp4,.avi,.mov,.mkv';

export default function ObjectTracking() {
  const [file, setFile] = useState(null);
  const [conf, setConf] = useState(0.3);
  const [iou, setIou] = useState(0.45);
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
      const created = await api.startVideoJob('track', file, { conf, iou, imgsz: 640 }, setUploadPct);
      setJob(created);
      pollRef.current = setInterval(async () => {
        try {
          const updated = await api.getJob(created.job_id);
          setJob(updated);
          if (updated.status === 'completed' || updated.status === 'failed') clearInterval(pollRef.current);
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
  const tracks = job?.stats?.tracks || [];
  const classData = job?.stats?.per_class
    ? Object.entries(job.stats.per_class).map(([name, count]) => ({ name, count }))
    : [];

  return (
    <div>
      <PageHeader
        title="Object Tracking"
        description="ByteTrack (tracker=bytetrack.yaml, persist=True) assigns a stable ID to every detection of your trained YOLO model across frames. Boxes, IDs, trajectories and counts are all computed from those real detections."
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
          <button type="button" className="btn btn-primary" disabled={!file || uploadPct != null} onClick={start}>
            ⚙ Track objects
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
            label={job.progress != null ? `Tracking… ${job.progress}%` : 'Tracking… (counting frames)'}
          />
        </div>
      ) : null}

      {job?.status === 'failed' ? (
        <ErrorAlert error={{ message: job.error || 'The tracking job failed on the server.', details: null }} title="Processing failed" />
      ) : null}

      {job?.status === 'completed' ? (
        <>
          <div className="grid grid-4">
            <StatCard label="Unique tracked objects" value={job.stats.unique_track_ids ?? '—'} accent />
            <StatCard label="Frames processed" value={job.frames_processed} />
            <StatCard label="Avg inference / frame" value={`${job.stats.avg_inference_ms} ms`} />
            <StatCard label="Processing speed" value={job.stats.processing_fps ? `${job.stats.processing_fps} FPS` : '—'} />
          </div>

          <section className="section">
            <h2>Tracked output (IDs + trajectories)</h2>
            <div className="card pad video-card">
              <video controls src={absoluteUrl(job.output.url)} preload="metadata" />
              <div className="row">
                <a className="btn btn-primary" href={`${absoluteUrl(job.output.url)}?download=1`}>
                  ⬇ Download tracked video
                </a>
                {job.stats.bytetrack_note ? <span className="muted">{job.stats.bytetrack_note}</span> : null}
              </div>
            </div>
          </section>

          <section className="section">
            <h2>Track summary (per ID)</h2>
            <div className="card">
              {tracks.length === 0 ? (
                <p className="pad muted" style={{ margin: 0 }}>
                  No persistent tracks — ByteTrack keeps IDs only when objects are detected consistently.
                </p>
              ) : (
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Track ID</th>
                        <th>Class</th>
                        <th>Frames seen</th>
                        <th>Avg confidence</th>
                        <th>Trajectory points</th>
                      </tr>
                    </thead>
                    <tbody>
                      {tracks.map((track) => (
                        <tr key={track.track_id}>
                          <td className="mono">#{track.track_id}</td>
                          <td><span className="chip">{track.class_name}</span></td>
                          <td>{track.frames}</td>
                          <td>{(track.avg_confidence * 100).toFixed(1)}%</td>
                          <td>{job.stats.trajectories?.[String(track.track_id)]?.length ?? 0}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </section>

          {classData.length > 0 ? (
            <section className="section">
              <h2>Detections per class (all frames combined)</h2>
              <div className="card pad">
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={classData} margin={{ top: 8, right: 16, left: -12, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1d2a45" />
                    <XAxis dataKey="name" stroke="#8b98ad" tick={{ fontSize: 12 }} interval={0} angle={-18} dy={8} />
                    <YAxis stroke="#8b98ad" tick={{ fontSize: 12 }} allowDecimals={false} />
                    <Tooltip contentStyle={{ background: '#0d1526', border: '1px solid #1d2a45', borderRadius: 8, color: '#e7eef9' }} />
                    <Bar dataKey="count" fill="#38bdf8" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>
          ) : null}
        </>
      ) : null}

      {job == null && uploadPct == null ? (
        <div className="card pad muted">
          Upload a traffic video and press <strong>Track objects</strong>. ByteTrack runs on top of the actual YOLO
          detections — motion trails are drawn for every active ID and the summary table lists how long each object
          was tracked.
        </div>
      ) : null}
    </div>
  );
}
