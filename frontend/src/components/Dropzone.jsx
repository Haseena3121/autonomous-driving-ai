import { useRef, useState } from 'react';

/**
 * Drag & drop / click-to-browse upload zone (controlled: the parent owns `file`).
 */
export default function Dropzone({ file, onFile, accept, hint, label = 'Drop a file here or click to browse', disabled = false }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const pick = (selected) => {
    if (disabled) return;
    if (selected && selected.size > 0) onFile(selected);
  };

  return (
    <div>
      <div
        className={`dropzone ${dragging ? 'dragging' : ''} ${disabled ? 'disabled' : ''} ${file ? 'has-file' : ''}`}
        onClick={() => !disabled && inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          pick(event.dataTransfer.files?.[0]);
        }}
        role="button"
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') inputRef.current?.click();
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          hidden
          onChange={(event) => {
            pick(event.target.files?.[0]);
            event.target.value = '';
          }}
        />
        <div className="dropzone-icon" aria-hidden="true">⬆</div>
        <div className="dropzone-label">{label}</div>
        {hint ? <div className="dropzone-hint">{hint}</div> : null}
      </div>
      {file ? (
        <div className="file-chip">
          <span className="file-name" title={file.name}>{file.name}</span>
          <span className="file-size">{(file.size / (1024 * 1024)).toFixed(2)} MB</span>
          <button type="button" className="btn btn-ghost btn-sm" disabled={disabled} onClick={() => onFile(null)}>
            Remove
          </button>
        </div>
      ) : null}
    </div>
  );
}
