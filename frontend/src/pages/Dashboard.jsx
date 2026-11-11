import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api.js';
import ErrorAlert from '../components/ErrorAlert.jsx';
import PageHeader from '../components/PageHeader.jsx';
import Spinner from '../components/Spinner.jsx';
import StatCard from '../components/StatCard.jsx';
import StatusBadge from '../components/StatusBadge.jsx';

const MODULES = [
  { to: '/detection', icon: '🎯', title: 'Object Detection', text: 'Upload an image and run the actual trained YOLO model — boxes, classes, confidence, latency.' },
  { to: '/video-analysis', icon: '🎞️', title: 'Video Analysis', text: 'Frame-by-frame inference with live progress and a downloadable annotated video.' },
  { to: '/tracking', icon: '🔗', title: 'Object Tracking', text: 'ByteTrack IDs and motion trajectories computed from the real detections.' },
  { to: '/lane-detection', icon: '🛣️', title: 'Lane Detection', text: 'OpenCV Canny + Hough pipeline with lane-centre estimation, plus a deep comparison.' },
  { to: '/depth-estimation', icon: '🕳️', title: 'Depth Estimation', text: 'MiDaS relative depth maps with per-object read-outs from the trained detector.' },
  { to: '/simulation', icon: '🚗', title: 'Driving Simulation', text: 'CARLA live perception bridge and the separate ROS2 perception node.' },
];

function formatUptime(seconds) {
  if (seconds == null) return '—';
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export default function Dashboard() {
  const [health, setHealth] = useState(null);
  const [info, setInfo] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const [h, i] = await Promise.all([api.getHealth(), api.getModelInfo()]);
        if (!alive) return;
        setHealth(h);
        setInfo(i);
        setError(null);
        try {
          const recent = await api.listResults(6);
          if (alive) setJobs(recent.jobs);
        } catch {
          /* history is non-critical */
        }
      } catch (err) {
        if (alive) setError(err);
      } finally {
        if (alive) setLoading(false);
      }
    };
    load();
    const timer = setInterval(load, 15000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  if (loading) return <Spinner label="Connecting to the backend…" />;

  return (
    <div>
      <PageHeader
        title="Home Dashboard"
        description="This dashboard reads the live backend state — the model status below reflects whether your trained best.pt is actually loaded, never a simulated state."
      />

      <ErrorAlert error={error} title="Backend unreachable" onRetry={() => window.location.reload()} />

      <div className="grid grid-4">
        <StatCard label="Model status" value={<StatusBadge status={info?.status || 'not_loaded'} />} sub={info?.device ? `on ${String(info.device).toUpperCase()}${info.device_name ? ` · ${info.device_name}` : ''}` : undefined} />
        <StatCard label="Device" value={info?.device ? String(info.device).toUpperCase() : '—'} sub={info?.cuda_available ? 'CUDA available' : 'CPU inference'} />
        <StatCard label="Model classes" value={info?.class_count != null ? info.class_count : '—'} sub={info?.model_type ? `task: ${info.model_type}` : undefined} />
        <StatCard label="Server uptime" value={formatUptime(health?.uptime_s)} sub={health ? `API v${health.version}` : undefined} />
      </div>

      <section className="section">
        <h2>Perception modules</h2>
        <div className="grid grid-3">
          {MODULES.map((mod) => (
            <Link key={mod.to} to={mod.to} className="card module-card">
              <span className="module-icon" aria-hidden="true">{mod.icon}</span>
              <h3>{mod.title}</h3>
              <p>{mod.text}</p>
              <span className="module-cta">Open →</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="section">
        <h2>Recent analysis jobs</h2>
        {jobs.length === 0 ? (
          <div className="card pad">
            <p className="muted" style={{ margin: 0 }}>
              No video jobs yet. Processed videos from <Link to="/video-analysis">Video Analysis</Link> and{' '}
              <Link to="/tracking">Object Tracking</Link> appear here with their real progress and results.
            </p>
          </div>
        ) : (
          <div className="card">
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>File</th>
                    <th>Status</th>
                    <th>Frames</th>
                    <th>Started</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job) => (
                    <tr key={job.job_id}>
                      <td><span className="chip">{job.kind === 'track' ? 'Tracking' : 'Detection'}</span></td>
                      <td className="mono">{job.filename}</td>
                      <td><StatusBadge status={job.status} /></td>
                      <td>{job.frames_processed}{job.total_frames ? ` / ${job.total_frames}` : ''}</td>
                      <td>{job.created_at ? new Date(job.created_at * 1000).toLocaleString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
