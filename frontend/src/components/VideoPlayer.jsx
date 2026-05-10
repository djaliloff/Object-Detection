import React, { useEffect, useRef, useState, useCallback, useMemo, memo } from 'react';
import { WifiOff, RefreshCw } from 'lucide-react';
import BBoxOverlay from './BBoxOverlay.jsx';
import ZoneOverlay from './ZoneOverlay.jsx';
import { useAuthStore } from '../stores/authStore';
import { zonesAPI } from '../utils/api';

const API_BASE = `${window.location.protocol}//${window.location.hostname}:8000/api/v1`;
const WS_BASE  = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.hostname}:8000/ws/live`;

// Spinner auto-hide timeout (ms) in case onLoad never fires
const STREAM_TIMEOUT_MS = 6000;
// Detection update debounce (ms) — prevents React re-render storms from fast WS messages
const DETECTION_DEBOUNCE_MS = 80;

// Memoized overlays — won't re-render unless detections/zones actually change
const MemoZoneOverlay = memo(ZoneOverlay);
const MemoBBoxOverlay = memo(BBoxOverlay);

const VideoPlayer = ({ camera, showAI = true, className = '' }) => {
  const { token } = useAuthStore();

  /* ── State ──────────────────────────────────────────────── */
  const [detections, setDetections]   = useState([]);
  const [zones, setZones]             = useState([]);
  const [activeAlert, setActiveAlert] = useState(null);
  const [wsStatus, setWsStatus]       = useState('connecting');
  const [mjpegKey, setMjpegKey]       = useState(0);
  const [isLoading, setIsLoading]     = useState(true);
  const [streamError, setStreamError] = useState(false);
  const [videoRect, setVideoRect]     = useState({ top: 0, left: 0, width: '100%', height: '100%' });

  /* ── Refs ────────────────────────────────────────────────── */
  const wsRef              = useRef(null);
  const reconnectRef       = useRef(null);
  const mountedRef         = useRef(true);
  const containerRef       = useRef(null);
  const imgRef             = useRef(null);
  const spinnerTimerRef    = useRef(null);
  const rectRetryRef       = useRef(null);
  // Detection debounce: buffer incoming WS data, flush after DETECTION_DEBOUNCE_MS
  const pendingDetectionsRef = useRef(null);
  const detectDebounceRef    = useRef(null);

  /* ── Derived ─────────────────────────────────────────────── */
  const cameraId   = camera?.id;
  const cameraName = camera?.name;

  const mjpegUrl = useMemo(
    () => (cameraId ? `${API_BASE}/cameras/${cameraId}/mjpeg` : ''),
    [cameraId]
  );

  /* ── Overlay coordinate alignment ────────────────────────── */
  const updateVideoRect = useCallback(() => {
    if (!imgRef.current || !containerRef.current) return;
    const container = containerRef.current.getBoundingClientRect();
    const img = imgRef.current;
    const iW = img.naturalWidth || img.width;
    const iH = img.naturalHeight || img.height;
    if (!iW || !iH) {
      // naturalWidth is 0 before first MJPEG frame — retry shortly
      clearTimeout(rectRetryRef.current);
      rectRetryRef.current = setTimeout(updateVideoRect, 400);
      return;
    }
    const cR = container.width / container.height;
    const mR = iW / iH;
    let w, h, t, l;
    if (cR > mR) {
      h = container.height; w = h * mR; t = 0; l = (container.width - w) / 2;
    } else {
      w = container.width; h = w / mR; l = 0; t = (container.height - h) / 2;
    }
    setVideoRect({
      top:    `${(t / container.height) * 100}%`,
      left:   `${(l / container.width)  * 100}%`,
      width:  `${(w / container.width)  * 100}%`,
      height: `${(h / container.height) * 100}%`,
    });
  }, []);

  useEffect(() => {
    const obs = new ResizeObserver(updateVideoRect);
    if (containerRef.current) obs.observe(containerRef.current);
    return () => { obs.disconnect(); clearTimeout(rectRetryRef.current); };
  }, [updateVideoRect]);

  /* ── Spinner timeout ─────────────────────────────────────── */
  const startSpinnerTimeout = useCallback(() => {
    clearTimeout(spinnerTimerRef.current);
    spinnerTimerRef.current = setTimeout(() => {
      if (mountedRef.current) setIsLoading(false);
    }, STREAM_TIMEOUT_MS);
  }, []);

  /* ── Debounced detection updater ─────────────────────────── */
  // Buffer fast WS messages and only trigger a React state update every
  // DETECTION_DEBOUNCE_MS ms. This prevents re-render storms when the AI
  // engine publishes detections faster than the browser can paint.
  const flushDetections = useCallback(() => {
    if (pendingDetectionsRef.current !== null && mountedRef.current) {
      setDetections(pendingDetectionsRef.current);
      pendingDetectionsRef.current = null;
    }
  }, []);

  const scheduleDetectionUpdate = useCallback((incoming) => {
    pendingDetectionsRef.current = incoming;
    clearTimeout(detectDebounceRef.current);
    detectDebounceRef.current = setTimeout(flushDetections, DETECTION_DEBOUNCE_MS);
  }, [flushDetections]);

  /* ── WebSocket ───────────────────────────────────────────── */
  const connect = useCallback(() => {
    if (!mountedRef.current || !cameraId) return;
    try {
      const url = token ? `${WS_BASE}?token=${token}` : WS_BASE;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return ws.close();
        setWsStatus('connected');
        ws.send(JSON.stringify({ type: 'subscribe', camera_id: cameraId }));
      };

      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          if (msg.type === 'detection' && msg.camera_id === cameraId) {
            // Buffer and debounce — don't setState on every message
            scheduleDetectionUpdate(msg.detections ?? []);
          } else if (msg.event_type && msg.camera_id === cameraId) {
            if (mountedRef.current) {
              setActiveAlert({
                type: msg.event_type,
                message: msg.event_data?.zone_name
                  ? `INTRUSION: ${msg.event_data.zone_name}`
                  : `ALERT: ${msg.event_type}`,
                timestamp: Date.now(),
              });
            }
          }
        } catch (_) { /* ignore parse errors */ }
      };

      ws.onclose = () => {
        if (!mountedRef.current) return;
        setWsStatus('disconnected');
        reconnectRef.current = setTimeout(connect, 4000);
      };

      ws.onerror = () => { if (mountedRef.current) setWsStatus('error'); };
    } catch (_) {
      setWsStatus('error');
    }
  }, [cameraId, token, scheduleDetectionUpdate]);

  useEffect(() => {
    mountedRef.current = true;
    if (cameraId) {
      connect();
      zonesAPI.getZones(cameraId).then(res => { if (mountedRef.current) setZones(res); }).catch(() => {});
    }
    return () => {
      mountedRef.current = false;
      clearTimeout(reconnectRef.current);
      clearTimeout(spinnerTimerRef.current);
      clearTimeout(detectDebounceRef.current);
      clearTimeout(rectRetryRef.current);
      wsRef.current?.close();
    };
  }, [connect, cameraId]);

  // Auto-clear alert after 5 s
  useEffect(() => {
    if (!activeAlert) return;
    const t = setTimeout(() => { if (mountedRef.current) setActiveAlert(null); }, 5000);
    return () => clearTimeout(t);
  }, [activeAlert]);

  // Reset stream on camera switch
  useEffect(() => {
    setIsLoading(true);
    setStreamError(false);
    setDetections([]);
    setMjpegKey(k => k + 1);
    startSpinnerTimeout();
  }, [cameraId, startSpinnerTimeout]);

  if (!cameraId) return null;

  const handleRetry = () => {
    setStreamError(false);
    setIsLoading(true);
    setMjpegKey(k => k + 1);
    startSpinnerTimeout();
  };

  return (
    <div
      ref={containerRef}
      className={`relative w-full h-full bg-black overflow-hidden select-none ${className}`}
      id={`camera-player-${cameraId}`}
    >
      {!streamError ? (
        <>
          {/* ── MJPEG stream ─────────────────────────────────── */}
          <img
            key={mjpegKey}
            ref={imgRef}
            src={mjpegUrl}
            alt={`Feed ${cameraName}`}
            className="w-full h-full object-contain"
            // decoding="async" tells the browser to decode off the main thread
            decoding="async"
            onLoad={() => {
              clearTimeout(spinnerTimerRef.current);
              if (mountedRef.current) {
                setIsLoading(false);
                setStreamError(false);
              }
              updateVideoRect();
            }}
            onError={() => {
              clearTimeout(spinnerTimerRef.current);
              if (mountedRef.current) {
                setIsLoading(false);
                setStreamError(true);
              }
            }}
          />

          {/* ── Zone overlay ─────────────────────────────────── */}
          <div className="absolute pointer-events-none z-10" style={videoRect}>
            <MemoZoneOverlay zones={zones} />
          </div>

          {/* ── AI detection overlay ──────────────────────────── */}
          {showAI && (
            <div className="absolute pointer-events-none z-20" style={videoRect}>
              <MemoBBoxOverlay
                detections={detections}
                zones={zones}
                showTrajectory={false}
                showVelocity={false}
              />
            </div>
          )}

          {/* ── Alert HUD ────────────────────────────────────── */}
          {activeAlert && (
            <div className="absolute inset-0 pointer-events-none z-50 flex items-center justify-center">
              <div className="absolute inset-0 border-[6px] border-red-600/40 animate-pulse" />
              <div className="bg-red-600/90 backdrop-blur-xl px-6 py-3 rounded-2xl shadow-2xl flex flex-col items-center">
                <span className="text-white text-xl font-black uppercase tracking-tight">{activeAlert.message}</span>
                <span className="text-white/60 text-[9px] font-bold uppercase tracking-widest mt-1">Alert — Intervention Required</span>
              </div>
            </div>
          )}
        </>
      ) : (
        /* ── No signal / error state ─────────────────────────── */
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-neutral-900/80">
          <div className="flex flex-col items-center space-y-3">
            <div className="w-12 h-12 rounded-full bg-neutral-800 flex items-center justify-center border border-white/5">
              <WifiOff className="w-5 h-5 text-neutral-500" />
            </div>
            <p className="text-xs font-black text-white/60 uppercase tracking-widest">{cameraName}</p>
            <p className="text-[9px] text-neutral-500 uppercase tracking-wider">No Signal</p>
            <button
              onClick={handleRetry}
              className="flex items-center space-x-2 px-3 py-1.5 bg-blue-600/20 hover:bg-blue-600/40 border border-blue-500/30 rounded-xl text-blue-400 text-[9px] font-black uppercase tracking-widest transition-colors"
            >
              <RefreshCw className="w-3 h-3" />
              <span>Retry</span>
            </button>
          </div>
        </div>
      )}

      {/* ── Loading spinner ───────────────────────────────────── */}
      {isLoading && !streamError && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/60 z-30 space-y-2">
          <div className="w-8 h-8 border-2 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
          <p className="text-[8px] font-bold uppercase tracking-widest text-neutral-500">Connecting...</p>
        </div>
      )}

      {/* ── Status pill ──────────────────────────────────────── */}
      <div className="absolute bottom-2 right-2 z-40 flex items-center space-x-1.5">
        <div className={`flex items-center space-x-1 px-2 py-0.5 rounded-full border border-white/10 text-[7px] font-black uppercase tracking-widest ${
          wsStatus === 'connected' ? 'bg-green-500/10 text-green-400' : 'bg-neutral-800 text-neutral-500'
        }`}>
          <div className={`w-1.5 h-1.5 rounded-full ${wsStatus === 'connected' ? 'bg-green-500 animate-pulse' : 'bg-neutral-600'}`} />
          <span>AI {wsStatus}</span>
        </div>
        {detections.length > 0 && (
          <div className="px-2 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-300 text-[7px] font-black uppercase tracking-widest">
            {detections.filter(d => d.track_id != null && d.track_id >= 0).length} tracked
          </div>
        )}
      </div>
    </div>
  );
};

export default VideoPlayer;