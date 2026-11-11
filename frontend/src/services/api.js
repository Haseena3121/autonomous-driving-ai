/**
 * REST client for the ADAS Flask backend.
 *
 * Every backend response uses the envelope { success, data } or
 * { success: false, error: { code, message, ... } } — this module unwraps
 * `data` and turns failures into typed ApiError objects the pages render.
 */

// In production (Flask serves both API + static files) BASE_URL is empty
// so all requests are same-origin.  In dev, the Vite proxy handles /api.
// For split deployment, set VITE_API_URL to the backend origin.
const BASE_URL = import.meta.env.VITE_API_URL ?? '';

export class ApiError extends Error {
  constructor(message, status = 0, code = 'UNKNOWN', details = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details; // full backend error object (may include instructions[])
  }
}

async function parseResponse(res) {
  const text = await res.text();
  let body = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    /* non-JSON response body */
  }
  if (!res.ok || (body && body.success === false)) {
    const message =
      body?.error?.message ||
      (res.status === 0 ? 'Network error' : `Request failed (HTTP ${res.status})`);
    throw new ApiError(message, res.status, body?.error?.code || 'HTTP_ERROR', body?.error || null);
  }
  return body?.data !== undefined ? body.data : body;
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${BASE_URL}${path}`, options);
  } catch {
    throw new ApiError(
      'Cannot reach the backend API. Is the Flask server running? Start it with "python app.py" in backend/.',
      0,
      'NETWORK'
    );
  }
  return parseResponse(res);
}

const get = (path) => request(path);
const post = (path, body) =>
  request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
const postForm = (path, formData) => request(path, { method: 'POST', body: formData });

/** XHR upload with real progress callbacks (fetch cannot report upload progress). */
export function uploadWithProgress(path, formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${BASE_URL}${path}`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      let body = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* ignore */
      }
      if (xhr.status >= 200 && xhr.status < 300 && body?.success !== false) {
        resolve(body?.data !== undefined ? body.data : body);
      } else {
        reject(
          new ApiError(
            body?.error?.message || `Upload failed (HTTP ${xhr.status})`,
            xhr.status,
            body?.error?.code || 'HTTP_ERROR',
            body?.error || null
          )
        );
      }
    };
    xhr.onerror = () =>
      reject(
        new ApiError(
          'Cannot reach the backend API. Is the Flask server running? Start it with "python app.py" in backend/.',
          0,
          'NETWORK'
        )
      );
    xhr.send(formData);
  });
}

export const absoluteUrl = (path) =>
  path && path.startsWith('/') ? `${BASE_URL}${path}` : path;

export const simulationFrameUrl = () => `${BASE_URL}/api/simulation/frame?t=${Date.now()}`;

function imageForm(file) {
  const fd = new FormData();
  fd.append('image', file);
  return fd;
}

function appendParams(fd, params) {
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') fd.append(key, String(value));
  });
  return fd;
}

export const api = {
  // core
  getHealth: () => get('/api/health'),
  getModelInfo: () => get('/api/model/info'),
  reloadModel: () => post('/api/model/reload'),
  getPerformance: () => get('/api/performance'),
  runBenchmark: ({ runs = 10, imgsz = 640 } = {}) => post('/api/performance/benchmark', { runs, imgsz }),
  listResults: (limit = 10) => get(`/api/results?limit=${limit}`),
  getJob: (jobId) => get(`/api/results/${jobId}`),

  // detection
  detectImage: (file, { conf = 0.25, iou = 0.45, imgsz = 640 } = {}) =>
    postForm('/api/detect/image', appendParams(imageForm(file), { conf, iou, imgsz })),
  startVideoJob: (kind, file, { conf = 0.25, iou = 0.45, imgsz = 640 } = {}, onProgress) => {
    const fd = new FormData();
    fd.append('video', file);
    appendParams(fd, { conf, iou, imgsz });
    const path = kind === 'track' ? '/api/track/video' : '/api/detect/video';
    return onProgress ? uploadWithProgress(path, fd, onProgress) : postForm(path, fd);
  },

  // lane
  laneDetect: (file, { cannyLow = 50, cannyHigh = 150, steps = true } = {}) =>
    postForm('/api/lane/detect', appendParams(imageForm(file), { canny_low: cannyLow, canny_high: cannyHigh, steps })),
  laneDeep: (file, { threshold = 0.5 } = {}) =>
    postForm('/api/lane/deep', appendParams(imageForm(file), { threshold })),

  // depth
  depthEstimate: (file, { withObjects = true } = {}) =>
    postForm('/api/depth/estimate', appendParams(imageForm(file), { with_objects: withObjects ? 1 : 0 })),
  depthStatus: () => get('/api/depth/status'),

  // simulation
  simulationStatus: () => get('/api/simulation/status'),
  simulationConnect: (host, port) => post('/api/simulation/connect', { host, port }),
  simulationDisconnect: () => post('/api/simulation/disconnect'),
  ros2Status: () => get('/api/ros2/status'),

  // doubts chat
  sendChatMessage: (message, history = []) => post('/api/chat', { message, history }),

  // auth
  login: (userId, password) => post('/api/auth/login', { user_id: userId, password }),
  register: (userId, password, name, email) =>
    post('/api/auth/register', { user_id: userId, password, name, email }),
  getAuthMe: () => get('/api/auth/me'),
};
