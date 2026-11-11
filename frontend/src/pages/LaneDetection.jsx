import { useState } from 'react';
import { absoluteUrl, api } from '../services/api.js';
import CodeBlock from '../components/CodeBlock.jsx';
import Disclaimer from '../components/Disclaimer.jsx';
import Dropzone from '../components/Dropzone.jsx';
import ErrorAlert from '../components/ErrorAlert.jsx';
import ImageResult from '../components/ImageResult.jsx';
import PageHeader from '../components/PageHeader.jsx';
import Spinner from '../components/Spinner.jsx';
import StatusBadge from '../components/StatusBadge.jsx';

const ACCEPT = 'image/png,image/jpeg,image/bmp,image/webp';

function MetaPanel({ meta }) {
  if (!meta) return null;
  return (
    <div className="card pad">
      <h3 style={{ marginTop: 0 }}>Pipeline output</h3>
      <div className="kv-grid">
        <div className="kv"><span>Lanes detected</span><StatusBadge status={meta.lanes_detected === 'both' ? 'ok' : meta.lanes_detected === 'none' ? 'none' : 'loading'} label={meta.lanes_detected} /></div>
        <div className="kv"><span>Hough segments</span><strong>{meta.hough_segments}</strong></div>
        <div className="kv"><span>Image centre</span><strong>{meta.image_center_px} px</strong></div>
        <div className="kv"><span>Lane centre</span><strong>{meta.lane_center_px != null ? `${meta.lane_center_px} px` : '— (needs both lanes)'}</strong></div>
        <div className="kv">
          <span>Offset from centre</span>
          <strong>
            {meta.offset_px != null ? `${meta.offset_px} px (${meta.offset_direction})` : '—'}
          </strong>
        </div>
        <div className="kv"><span>Left line x@bottom</span><strong>{meta.left_line ? meta.left_line.x_at_bottom : '—'}</strong></div>
        <div className="kv"><span>Right line x@bottom</span><strong>{meta.right_line ? meta.right_line.x_at_bottom : '—'}</strong></div>
      </div>
      <p className="muted" style={{ marginBottom: 0 }}>{meta.note}</p>
    </div>
  );
}

export default function LaneDetection() {
  // classic OpenCV pipeline
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [cannyLow, setCannyLow] = useState(50);
  const [cannyHigh, setCannyHigh] = useState(150);
  const [withSteps, setWithSteps] = useState(true);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // deep segmentation comparison
  const [deepFile, setDeepFile] = useState(null);
  const [deepBusy, setDeepBusy] = useState(false);
  const [deepResult, setDeepResult] = useState(null);
  const [deepError, setDeepError] = useState(null);

  const readPreview = (f) => (f ? URL.createObjectURL(f) : null);
  const [deepPreview, setDeepPreview] = useState(null);

  const runClassic = async () => {
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const data = await api.laneDetect(file, { cannyLow, cannyHigh, steps: withSteps });
      setResult(data);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const runDeep = async () => {
    if (!deepFile || deepBusy) return;
    setDeepBusy(true);
    setDeepError(null);
    setDeepResult(null);
    try {
      const data = await api.laneDeep(deepFile, { threshold: 0.5 });
      setDeepResult(data);
    } catch (err) {
      setDeepError(err);
    } finally {
      setDeepBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Lane Detection"
        description="The classical pipeline is pure OpenCV: grayscale → Gaussian blur → Canny edges → trapezoidal ROI → probabilistic Hough transform → left/right lane fit → lane-centre estimation. A separate deep-learning comparison module is provided below."
      />

      <div className="card pad">
        <Dropzone
          file={file}
          onFile={(f) => {
            setFile(f);
            setPreview(readPreview(f));
            setResult(null);
          }}
          accept={ACCEPT}
          label="Drop a road image here or click to browse"
          hint="Front-facing road scene — dashcam or driving frame"
        />
        <div className="controls">
          <label className="field">
            <span>Canny low: <strong>{cannyLow}</strong></span>
            <input type="range" min="10" max="300" step="10" value={cannyLow} onChange={(e) => setCannyLow(Number(e.target.value))} />
          </label>
          <label className="field">
            <span>Canny high: <strong>{cannyHigh}</strong></span>
            <input type="range" min="50" max="600" step="10" value={cannyHigh} onChange={(e) => setCannyHigh(Number(e.target.value))} />
          </label>
          <label className="field field-check">
            <input type="checkbox" checked={withSteps} onChange={(e) => setWithSteps(e.target.checked)} />
            <span>Show intermediate steps (edges & ROI)</span>
          </label>
          <button type="button" className="btn btn-primary" disabled={!file || busy} onClick={runClassic}>
            {busy ? 'Detecting…' : '▶ Detect lanes'}
          </button>
        </div>
      </div>

      {busy ? <Spinner label="Running the OpenCV lane pipeline…" /> : null}
      <ErrorAlert error={error} onRetry={file ? runClassic : undefined} />

      {result ? (
        <>
          <MetaPanel meta={result.meta} />
          <section className="section">
            <h2>Lane overlay</h2>
            <ImageResult
              originalSrc={preview}
              resultSrc={result.annotated_image}
              originalLabel="Original image"
              resultLabel="Detected lanes + centre"
              downloadUrl={absoluteUrl(result.annotated_url)}
              downloadName="adas-lanes.jpg"
            />
          </section>
          {result.steps ? (
            <section className="section">
              <h2>Intermediate steps</h2>
              <div className="grid grid-2">
                <figure className="image-figure">
                  <img src={result.steps.edges} alt="Canny edges" />
                  <figcaption>1–2 · Canny edges</figcaption>
                </figure>
                <figure className="image-figure">
                  <img src={result.steps.roi} alt="Region of interest mask" />
                  <figcaption>3 · Edges after region-of-interest mask</figcaption>
                </figure>
              </div>
            </section>
          ) : null}
        </>
      ) : null}

      <section className="section">
        <h2>Deep-learning comparison (ENet segmentation)</h2>
        <Disclaimer tone="info" title="How this module is labelled">
          This comparison runs a PyTorch ENet segmentation network. It only works when <em>you</em> trained it
          (<code>backend/models/lane_seg_enet.pth</code>, via <code>model_training/train_lane_enet.py</code>) — the UI
          then shows <strong>Trained by me</strong>. No pretrained network is silently substituted; if the checkpoint
          is missing you get an honest "not available" plus training instructions.
        </Disclaimer>

        <div className="card pad" style={{ marginTop: 16 }}>
          <Dropzone
            file={deepFile}
            onFile={(f) => {
              setDeepFile(f);
              setDeepPreview(readPreview(f));
              setDeepResult(null);
            }}
            accept={ACCEPT}
            label="Drop the same road image to compare"
            hint="Runs only if your trained ENet checkpoint exists"
          />
          <div className="controls">
            <button type="button" className="btn btn-primary" disabled={!deepFile || deepBusy} onClick={runDeep}>
              {deepBusy ? 'Segmenting…' : '▶ Run deep segmentation'}
            </button>
            {deepResult ? <StatusBadge status={deepResult.status.mode} /> : null}
          </div>
        </div>

        {deepBusy ? <Spinner label="Running ENet inference…" /> : null}
        <ErrorAlert error={deepError} onRetry={deepFile ? runDeep : undefined} />

        {deepResult ? (
          <>
            <div className="card pad">
              <div className="kv-grid">
                <div className="kv"><span>Model mode</span><StatusBadge status={deepResult.status.mode} /></div>
                <div className="kv"><span>Checkpoint</span><strong className="mono">{deepResult.status.checkpoint_path}</strong></div>
                <div className="kv"><span>Lane coverage</span><strong>{deepResult.meta.coverage_pct}% of pixels</strong></div>
                <div className="kv"><span>Device</span><strong>{String(deepResult.meta.device || 'cpu').toUpperCase()}</strong></div>
                <div className="kv"><span>Inference</span><strong>{deepResult.meta.inference_ms} ms</strong></div>
                {deepResult.status.trained_info ? (
                  <div className="kv"><span>Training info</span><strong>{JSON.stringify(deepResult.status.trained_info)}</strong></div>
                ) : null}
              </div>
            </div>
            <ImageResult
              originalSrc={deepPreview}
              resultSrc={deepResult.annotated_image}
              originalLabel="Original image"
              resultLabel="ENet lane mask overlay"
            />
          </>
        ) : null}

        <CodeBlock title="Train the comparison model yourself (optional)">
          {`# inside model_training/
python train_lane_enet.py --images dataset/lane/images --masks dataset/lane/masks --epochs 40
# -> writes backend/models/lane_seg_enet.pth
# -> the Lane Detection page then reports: mode = "trained_by_me"`}
        </CodeBlock>
      </section>
    </div>
  );
}
