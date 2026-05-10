import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { Activity, WifiOff, RefreshCw } from 'lucide-react';
import BBoxOverlay from './BBoxOverlay.jsx';
import ZoneOverlay from './ZoneOverlay.jsx';
import { useAuthStore } from '../stores/authStore';
import { zonesAPI } from '../utils/api';

/* ── Backend base URL ─────────────────────────────────────── */
const API_BASE = `${window.location.protocol}//${window.location.hostname}:8000/api/v1`;
const WS_BASE = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.hostname}:8000/ws/live`;

// How long (ms) before we give up waiting for the first frame and hide the spinner
const STREAM_TIMEOUT_MS = 6000;

const VideoPlayer = ({ camera, showAI = true, className = '' }) => {
  const { token } = useAuthStore();

  /* ── State ─────────────────────────────────────────────── */
  const [detections, setDetections] = useState([]);
  const [zones, setZones] = useState([]);
  const [activeAlert, setActiveAlert] = useState(null);
  const [wsStatus, setWsStatus] = useState('connecting');
  const [mjpegKey, setMjpegKey] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [streamError, setStreamError] = useState(false);
  const [videoRect, setVideoRect] = useState({ top: 0, left: 0, width: '100%', height: '100%' });

  /* ── Refs ──────────────────────────────────────────────── */
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);
  const mountedRef = useRef(true);
  const containerRef = useRef(null);
  const imgRef = useRef(null);
  const spinnerTimerRef = useRef(null);
  const rectRetryRef = useRef(null);

  /* ── Derived ────────────────────────────────────────────── */
  const cameraId = camera?.id;
  const cameraName = camera?.name;

  // Always attempt to stream — don't gate on camera.status.
  // The img onError handler will show the offline state if stream fails.
  const mjpegUrl = useMemo(
    () => (cameraId ? `${API_BASE}/cameras/${cameraId}/mjpeg` : ''),
    [cameraId]
  );

  /* ── Coordinate alignment ──────────────────────────────── */
  const updateVideoRect = useCallback(() => {
    if (!imgRef.current || !containerRef.current) return;
    const container = containerRef.current.getBoundingClientRect();
    const img = imgRef.current;
    const iW = img.naturalWidth || img.width;
    const iH = img.naturalHeight || img.height;
    if (!iW || !iH) {
      // Retry after a short delay — naturalWidth is 0 before first MJPEG frame
      clearTimeout(rectRetryRef.current);
      rectRetryRef.current = setTimeout(updateVideoRect, 300);
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
      top: `${(t / container.height) * 100}%`,
      left: `${(l / container.width) * 100}%`,
      width: `${(w / container.width) * 100}%`,
      height: `${(h / container.height) * 100}%`,
    });
  }, []);

  useEffect(() => {
    const obs = new ResizeObserver(updateVideoRect);
    if (containerRef.current) obs.observe(containerRef.current);
    return () => { obs.disconnect(); clearTimeout(rectRetryRef.current); };
  }, [updateVideoRect]);

  /* ── Spinner timeout ────────────────────────────────────── */
  // Auto-hide spinner after STREAM_TIMEOUT_MS so it doesn't block video forever
  const startSpinnerTimeout = useCallback(() => {
    clearTimeout(spinnerTimerRef.current);
    spinnerTimerRef.current = setTimeout(() => {
      if (mountedRef.current) setIsLoading(false);
    }, STREAM_TIMEOUT_MS);
  }, []);

  /* ── WebSocket (detections + alerts only) ──────────────── */
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
            setDetections(msg.detections ?? []);
          } else if (msg.event_type && msg.camera_id === cameraId) {
            setActiveAlert({
              type: msg.event_type,
              message: msg.event_data?.zone_name
                ? `INTRUSION: ${msg.event_data.zone_name}`
                : `ALERT: ${msg.event_type}`,
              timestamp: Date.now(),
            });
          }
        } catch (_) { /* ignore */ }
      };

      ws.onclose = () => {
        if (!mountedRef.current) return;
        setWsStatus('disconnected');
        reconnectRef.current = setTimeout(connect, 4000);
      };

      ws.onerror = () => setWsStatus('error');
    } catch (_) {
      setWsStatus('error');
    }
  }, [cameraId, token]);

  useEffect(() => {
    mountedRef.current = true;
    if (cameraId) {
      connect();
      zonesAPI.getZones(cameraId).then(res => setZones(res)).catch(() => { });
    }
    return () => {
      mountedRef.current = false;
      clearTimeout(reconnectRef.current);
      clearTimeout(spinnerTimerRef.current);
      wsRef.current?.close();
    };
  }, [connect, cameraId]);

  // Clear alert after 5 s
  useEffect(() => {
    if (activeAlert) {
      const t = setTimeout(() => setActiveAlert(null), 5000);
      return () => clearTimeout(t);
    }
  }, [activeAlert]);

  // Reset on camera switch
  useEffect(() => {
    setIsLoading(true);
    setStreamError(false);
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
      {/* ── MJPEG stream — always attempt regardless of camera.status ── */}
      {!streamError ? (
        <>
          <img
            key={mjpegKey}
            ref={imgRef}
            src={mjpegUrl}
            alt={`Flux ${cameraName}`}
            className="w-full h-full object-contain"
            onLoad={() => {
              clearTimeout(spinnerTimerRef.current);
              setIsLoading(false);
              setStreamError(false);
              updateVideoRect();
            }}
            onError={() => {
              clearTimeout(spinnerTimerRef.current);
              setIsLoading(false);
              setStreamError(true);
            }}
          />

          {/* ── Zones Overlay ────────────────────────────────── */}
          <div className="absolute pointer-events-none z-10" style={videoRect}>
            <ZoneOverlay zones={zones} />
          </div>

          {/* ── BBox + MOT Tracking Layer ─────────────────────── */}
          {showAI && (
            <div className="absolute pointer-events-none z-20" style={videoRect}>
              <BBoxOverlay detections={detections} zones={zones} showTrajectory={false} showVelocity={false} />
            </div>
          )}

          {/* ── Alert HUD ────────────────────────────────────── */}
          {activeAlert && (
            <div className="absolute inset-0 pointer-events-none z-50 flex items-center justify-center">
              <div className="absolute inset-0 border-[8px] border-red-600/40 animate-pulse shadow-[inset_0_0_100px_rgba(220,38,38,0.4)]" />
              <div className="bg-red-600/90 backdrop-blur-xl px-8 py-4 rounded-[32px] shadow-2xl flex flex-col items-center animate-in zoom-in-95 slide-in-from-top-10 duration-300">
                <span className="text-white text-2xl font-black uppercase tracking-tighter">{activeAlert.message}</span>
                <span className="text-white/60 text-[10px] font-bold uppercase tracking-widest mt-1">Tactical Intervention Required</span>
              </div>
            </div>
          )}
        </>
      ) : (
        /* ── Stream Error / Offline state ─────────────────── */
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-neutral-900/80 backdrop-blur-sm">
          <div className="flex flex-col items-center space-y-3 animate-in fade-in zoom-in duration-500">
            <div className="w-14 h-14 rounded-full bg-neutral-800 flex items-center justify-center border border-white/5">
              <WifiOff className="w-6 h-6 text-neutral-500" />
            </div>
            <p className="text-xs font-black text-white/70 uppercase tracking-widest">{cameraName}</p>
            <p className="text-[9px] font-bold uppercase tracking-[0.15em] text-neutral-500">No Signal</p>
            <button
              onClick={handleRetry}
              className="flex items-center space-x-2 px-4 py-2 mt-2 bg-blue-600/20 hover:bg-blue-600/40 border border-blue-500/30 rounded-xl text-blue-400 text-[10px] font-black uppercase tracking-widest transition-all"
            >
              <RefreshCw className="w-3 h-3" />
              <span>Retry</span>
            </button>
          </div>
        </div>
      )}

      {/* ── Loading Spinner ──────────────────────────────────── */}
      {isLoading && !streamError && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/70 z-30 space-y-3">
          <div className="w-10 h-10 border-2 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
          <p className="text-[9px] font-black uppercase tracking-widest text-neutral-500">Connecting stream...</p>
        </div>
      )}

      {/* ── Status Indicators ────────────────────────────────── */}
      <div className="absolute bottom-3 right-3 z-40 flex items-center space-x-2">
        <div className={`flex items-center space-x-1.5 px-2 py-1 rounded-full backdrop-blur-xl border border-white/10 ${wsStatus === 'connected' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-500'
          }`}>
          <div className={`w-1.5 h-1.5 rounded-full ${wsStatus === 'connected' ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
          <span className="text-[8px] font-black uppercase tracking-[0.2em]">AI {wsStatus}</span>
        </div>
        {detections.length > 0 && (
          <div className="flex items-center space-x-1.5 px-2 py-1 rounded-full bg-cyan-500/10 backdrop-blur-xl border border-cyan-500/20 text-cyan-300">
            <span className="text-[8px] font-black uppercase tracking-[0.2em]">
              {detections.filter(d => d.track_id != null && d.track_id >= 0).length} TRACKED
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

export default VideoPlayer;