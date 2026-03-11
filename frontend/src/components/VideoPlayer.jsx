import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { Activity, WifiOff } from 'lucide-react';
import BBoxOverlay from './BBoxOverlay.jsx';
import { useAuthStore } from '../stores/authStore';

/* ── Stream Type Detection ─────────────────────────────────── */
function isMjpegUrl(url = '') {
  if (!url) return false;
  const u = url.toLowerCase();
  return (
    u.includes('/video') ||
    u.includes('/mjpeg') ||
    u.includes('/stream') ||
    u.includes('/videofeed') ||
    u.match(/:\d{4,5}\/?$/)
  ) || u.startsWith('http');
}

function snapshotUrl(streamUrl = '') {
  if (!streamUrl) return '';
  const base = streamUrl.replace(/\/video.*$/, '').replace(/\/$/, '');
  return `${base}/shot.jpg`;
}

/* ── WebSocket Base URL ────────────────────────────────────── */
const WS_BASE = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.hostname}:8000/ws/live`;

const VideoPlayer = ({ camera, className = "" }) => {
  const { token } = useAuthStore();
  const [detections, setDetections] = useState([]);
  const [wsStatus, setWsStatus] = useState('connecting');
  const [imgError, setImgError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const wsRef = useRef(null);
  const reconnectRef = useRef(null);
  const mountedRef = useRef(true);

  const cameraId = camera?.id;
  const cameraStatus = camera?.status;
  const cameraName = camera?.name;

  /* ── WebSocket for Bounding Boxes ─────────────────────────── */
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
          }
        } catch (e) { /* ignore */ }
      };

      ws.onclose = () => {
        if (!mountedRef.current) return;
        setWsStatus('disconnected');
        reconnectRef.current = setTimeout(connect, 4000);
      };

      ws.onerror = () => setWsStatus('error');
    } catch (e) {
      setWsStatus('error');
    }
  }, [cameraId, token]);

  useEffect(() => {
    mountedRef.current = true;
    if (cameraId) {
      connect();
    }
    return () => {
      mountedRef.current = false;
      clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, [connect, cameraId]);

  // Check stream_url or fallback fields including nested config objects
  const streamUrl = camera?.stream_url 
    || camera?.mjpeg_url 
    || camera?.hls_url 
    || camera?.config_json?.stream_url 
    || camera?.config?.stream_url 
    || camera?.config_json?.mjpeg_url 
    || camera?.config?.mjpeg_url
    || camera?.rtsp_url 
    || '';
  const isMjpeg = useMemo(() => isMjpegUrl(streamUrl), [streamUrl]);

  if (!cameraId) return null;

  const isOnline = cameraStatus === 'online';

  return (
    <div className={`relative w-full h-full bg-black overflow-hidden select-none ${className}`} id={`camera-player-${cameraId}`}>
      
      {/* ── Video Stream ─────────────────────────────────────────── */}
      {isOnline ? (
        <>
          {isMjpeg ? (
            imgError ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-neutral-900 gap-4">
                <WifiOff className="w-12 h-12 text-red-500/50" />
                <div className="text-center">
                  <p className="text-sm font-bold text-neutral-400">Tactical Feed Lost</p>
                  <p className="text-[10px] text-neutral-600 font-mono mt-1">{streamUrl}</p>
                </div>
                <button
                  className="mt-2 px-4 py-2 bg-blue-600/20 text-blue-400 border border-blue-500/30 rounded-lg text-xs font-black uppercase tracking-widest hover:bg-blue-600/30 transition-all"
                  onClick={() => setImgError(false)}
                >
                  Regain Link
                </button>
              </div>
            ) : (
              <img
                src={streamUrl}
                alt={`Flux ${cameraName}`}
                className="w-full h-full object-cover"
                onLoad={() => setIsLoading(false)}
                onError={(e) => {
                  console.error('Stream load error:', streamUrl);
                  setImgError(true);
                  setIsLoading(false);
                }}
              />
            )
          ) : (
            <video
              src={streamUrl}
              autoPlay muted playsInline
              className="w-full h-full object-cover"
              onPlaying={() => setIsLoading(false)}
              onError={(e) => {
                setImgError(true);
                setIsLoading(false);
                e.target.style.display = 'none';
              }}
            />
          )}

          {/* ── BBox Layer ────────────────────────────────────────── */}
          <BBoxOverlay detections={detections} />
        </>
      ) : (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-neutral-900/80 backdrop-blur-3xl overflow-hidden">
           {isMjpeg && streamUrl && (
              <img
                src={snapshotUrl(streamUrl)}
                alt="snapshot"
                className="absolute inset-0 w-full h-full object-cover opacity-20 grayscale scale-105 pointer-events-none"
                onError={(e) => { e.target.style.display = 'none'; }}
              />
           )}
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

      {/* ── Loading Spinner ─────────────────────────────────────── */}
      {isOnline && isLoading && !imgError && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/60 backdrop-blur-sm z-30">
          <div className="w-12 h-12 border-2 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
        </div>
      )}

      {/* ── Matrix Status Indicators ───────────────────────────── */}
      <div className="absolute bottom-6 right-6 z-40 flex items-center space-x-3">
          <div className={`flex items-center space-x-2 px-3 py-1 rounded-full backdrop-blur-xl border border-white/10 ${
            wsStatus === 'connected' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-500'
          }`}>
             <div className={`w-1.5 h-1.5 rounded-full ${wsStatus === 'connected' ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
             <span className="text-[8px] font-black uppercase tracking-[0.2em]">IA {wsStatus}</span>
          </div>
          
          <div className="flex items-center space-x-2 px-3 py-1 rounded-full bg-white/5 backdrop-blur-xl border border-white/10 text-neutral-400">
             <span className="text-[8px] font-black uppercase tracking-[0.2em]">
                {detections.length > 0 ? `${detections.length} TRKS` : (isMjpeg ? 'MJPEG' : 'STREAM')}
             </span>
          </div>
      </div>
    </div>
  );
};

export default VideoPlayer;
