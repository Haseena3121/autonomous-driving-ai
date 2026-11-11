/** Side-by-side input/result viewer with optional download link. */
export default function ImageResult({ originalSrc, resultSrc, originalLabel = 'Original', resultLabel = 'Result', downloadUrl, downloadName }) {
  return (
    <div className="image-result">
      {originalSrc ? (
        <figure className="image-figure">
          <img src={originalSrc} alt={originalLabel} />
          <figcaption>{originalLabel}</figcaption>
        </figure>
      ) : null}
      {resultSrc ? (
        <figure className="image-figure image-figure-result">
          <img src={resultSrc} alt={resultLabel} />
          <figcaption>{resultLabel}</figcaption>
        </figure>
      ) : null}
      {downloadUrl ? (
        <div className="row" style={{ gridColumn: '1 / -1' }}>
          <a className="btn btn-primary" href={downloadUrl} download={downloadName || true} target="_blank" rel="noreferrer">
            ⬇ Download result
          </a>
        </div>
      ) : null}
    </div>
  );
}
