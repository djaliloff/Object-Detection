import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { Activity, WifiOff, ShieldAlert } from 'lucide-react';
import BBoxOverlay from './BBoxOverlay.jsx';
import ZoneOverlay from './ZoneOverlay.jsx';
import { useAuthStore } from '../stores/authStore';
import { zonesAPI } from '../utils/api';

/* ── Backend base URL ─────────────────────────────────────── */
const API_BASE = `${window.location.protocol}//${window.location.hostname}:8000/api/v1`;
const WS_BASE  = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.hostname}:8000/ws/live`;

const VideoPlayer = ({ camera, showAI = true, className = '' }) => {
  const { token } = useAuthStore();

  /* ── State ─────────────────────────────────────────────── */
  const [detections, setDetections]   = useState([]);
  const [zones, setZones]             = useState([]);
  const [activeAlert, setActiveAlert] = useState(null);
  const [wsStatus, setWsStatus]       = useState('connecting');
  const [mjpegKey, setMjpegKey]       = useState(0); // bump to force img reload
  const [isLoading, setIsLoading]     = useState(true);
  const [videoRect, setVideoRect]     = useState({ top: 0, left: 0, width: '100%', height: '100%' });

  /* ── Refs ──────────────────────────────────────────────── */
  const wsRef        = useRef(null);
  const reconnectRef = useRef(null);
  const mountedRef   = useRef(true);
  const containerRef = useRef(null);
  const imgRef       = useRef(null);

  /* ── Derived ────────────────────────────────────────────── */
  const cameraId     = camera?.id;
  const cameraName   = camera?.name;
  const cameraStatus = camera?.status;
  const isOnline     = cameraStatus === 'online';

  // The MJPEG stream URL is always the backend endpoint — the gateway feeds it
  // for every camera regardless of source type (mp4, rtsp, mjpeg, thermal, etc.)
  const mjpegUrl = useMemo(
    () => (cameraId ? `${API_BASE}/cameras/${cameraId}/mjpeg` : ''),
    [cameraId]
  );

  /* ── Coordinate alignment ──────────────────────────────── */
  const updateVideoRect = useCallback(() => {
    if (!imgRef.current || !containerRef.current) return;
    const container = containerRef.current.getBoundingClientRect();
    const img = imgRef.current;
    const iW = img.naturalWidth;
    const iH = img.naturalHeight;
    if (!iW || !iH) return;
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
    return () => obs.disconnect();
  }, [updateVideoRect]);

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
      zonesAPI.getZones(cameraId).then(res => setZones(res)).catch(() => {});
    }
    return () => {
      mountedRef.current = false;
      clearTimeout(reconnectRef.current);
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
    setMjpegKey(k => k + 1);
  }, [cameraId]);

  if (!cameraId) return null;

  return (
    <div
      ref={containerRef}
      className={`relative w-full h-full bg-black overflow-hidden select-none ${className}`}
      id={`camera-player-${cameraId}`}
    >
      {isOnline ? (
        <>
          {/* ── MJPEG stream <img> — works for ALL camera types ── */}
          <img
            key={mjpegKey}
            ref={imgRef}
            src={mjpegUrl}
            alt={`Flux ${cameraName}`}
            className="w-full h-full object-contain"
            onLoad={() => {
              setIsLoading(false);
              updateVideoRect();
            }}
            onError={() => {
              // Don't hard-error — gateway catches up after a few seconds.
              // Just hide the spinner; the img tag itself keeps retrying the stream.
              setIsLoading(false);
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
                <ShieldAlert className="w-12 h-12 text-white mb-2 animate-bounce" />
                <span className="text-white text-2xl font-black uppercase tracking-tighter">{activeAlert.message}</span>
                <span className="text-white/60 text-[10px] font-bold uppercase tracking-widest mt-1">Tactical Intervention Required</span>
              </div>
            </div>
          )}
        </>
      ) : (
        /* ── Offline state ──────────────────────────────── */
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-neutral-900/80 backdrop-blur-3xl overflow-hidden">
          <div className="relative z-10 flex flex-col items-center animate-in fade-in zoom-in duration-500">
            <div className="w-16 h-16 rounded-full bg-neutral-800 flex items-center justify-center mb-6 shadow-2xl border border-white/5">
              <Activity className="w-8 h-8 text-neutral-600 animate-pulse" />
            </div>
            <h3 className="text-lg font-black text-white uppercase tracking-tighter mb-1">{cameraName}</h3>
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-neutral-500 bg-neutral-800/50 px-3 py-1 rounded-full border border-white/5">
              Node Deactivated
            </p>
          </div>
        </div>
      )}

      {/* ── Loading Spinner ──────────────────────────────── */}
      {isOnline && isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/60 backdrop-blur-sm z-30">
          <div className="w-12 h-12 border-2 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
        </div>
      )}

      {/* ── Status Indicators ────────────────────────────── */}
      <div className="absolute bottom-6 right-6 z-40 flex items-center space-x-3">
        <div className={`flex items-center space-x-2 px-3 py-1 rounded-full backdrop-blur-xl border border-white/10 ${
          wsStatus === 'connected' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-500'
        }`}>
          <div className={`w-1.5 h-1.5 rounded-full ${wsStatus === 'connected' ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
          <span className="text-[8px] font-black uppercase tracking-[0.2em]">IA {wsStatus}</span>
        </div>
        {detections.length > 0 && (
          <div className="flex items-center space-x-2 px-3 py-1 rounded-full bg-cyan-500/10 backdrop-blur-xl border border-cyan-500/20 text-cyan-300">
            <span className="text-[8px] font-black uppercase tracking-[0.2em]">
              {detections.filter(d => d.track_id != null && d.track_id >= 0).length} TRACKED
            </span>
          </div>
        )}
        <div className="flex items-center space-x-2 px-3 py-1 rounded-full bg-white/5 backdrop-blur-xl border border-white/10 text-neutral-400">
          <span className="text-[8px] font-black uppercase tracking-[0.2em]">
            {detections.length > 0 ? `${detections.length} DET` : 'STREAM'}
          </span>
        </div>
      </div>
    </div>
  );
};

export default VideoPlayer;
