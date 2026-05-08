import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { Activity, WifiOff, ShieldAlert } from 'lucide-react';
import BBoxOverlay from './BBoxOverlay.jsx';
import ZoneOverlay from './ZoneOverlay.jsx';
import { useAuthStore } from '../stores/authStore';
import { zonesAPI } from '../utils/api';

/* ── Stream Type Detection ─────────────────────────────────── */
const isMjpegUrl = (url = '') => {
  if (!url) return false;
  const u = url.toLowerCase();
  // If it's a known video/streaming extension, it's NOT MJPEG
  if (u.endsWith('.mp4') || u.endsWith('.mkv') || u.endsWith('.avi') || u.endsWith('.webm') || u.endsWith('.m3u8')) {
    return false;
  }
  return u.includes('/video') || u.includes('/mjpeg') || u.includes('/stream') || u.includes('/videofeed') || u.match(/:\d{4,5}\/?$/) || (u.startsWith('http') && !u.includes('.mp4'));
};

function snapshotUrl(streamUrl = '') {
  if (!streamUrl) return '';
  const base = streamUrl.replace(/\/video.*$/, '').replace(/\/$/, '');
  return `${base}/shot.jpg`;
}

/* ── WebSocket Base URL ────────────────────────────────────── */
const WS_BASE = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.hostname}:8000/ws/live`;

const VideoPlayer = ({ camera, showAI = true, className = "" }) => {
  const { token } = useAuthStore();
  const [detections, setDetections] = useState([]);
  const [zones, setZones] = useState([]);
  const [activeAlert, setActiveAlert] = useState(null); // { type, message, timestamp }
  const [wsStatus, setWsStatus] = useState('connecting');
  const [imgError, setImgError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [videoRect, setVideoRect] = useState({ top: 0, left: 0, width: '100%', height: '100%' });
  const [lastAlertTime, setLastAlertTime] = useState(0);
  const [syncFrame, setSyncFrame] = useState(null);   // base64 annotated frame from AI
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);
  const mountedRef = useRef(true);
  const containerRef = useRef(null);
  const mediaRef = useRef(null);

  /* ── Coordinate Alignment Logic ────────────────────────────── */
  const updateVideoRect = useCallback(() => {
    if (!mediaRef.current || !containerRef.current) return;
    
    const container = containerRef.current.getBoundingClientRect();
    const media = mediaRef.current;
    
    let intrinsicWidth, intrinsicHeight;
    if (media.tagName === 'IMG') {
      intrinsicWidth = media.naturalWidth;
      intrinsicHeight = media.naturalHeight;
    } else {
      intrinsicWidth = media.videoWidth;
      intrinsicHeight = media.videoHeight;
    }
    
    if (!intrinsicWidth || !intrinsicHeight) return;
    
    const containerRatio = container.width / container.height;
    const mediaRatio = intrinsicWidth / intrinsicHeight;
    
    let w, h, t, l;
    if (containerRatio > mediaRatio) {
      h = container.height;
      w = h * mediaRatio;
      t = 0;
      l = (container.width - w) / 2;
    } else {
      w = container.width;
      h = w / mediaRatio;
      l = 0;
      t = (container.height - h) / 2;
    }
    
    setVideoRect({ 
      top: `${(t / container.height) * 100}%`, 
      left: `${(l / container.width) * 100}%`, 
      width: `${(w / container.width) * 100}%`, 
      height: `${(h / container.height) * 100}%` 
    });
  }, []);

  useEffect(() => {
    const observer = new ResizeObserver(updateVideoRect);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [updateVideoRect]);

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
            console.debug(`[LiveFeed] Detections received for ${cameraId}:`, msg.detections?.length);
            setDetections(msg.detections ?? []);
          } else if (msg.type === 'surveillance_frames' && msg.camera_id === cameraId) {
            // Annotated frame from AI engine — display directly (no lag)
            if (msg.image_data) setSyncFrame(msg.image_data);
          } else if (msg.event_type && msg.camera_id === cameraId) {
            console.warn(`[LiveFeed] ALERT DETECTED for ${cameraId}:`, msg.event_type);
            setActiveAlert({
              type: msg.event_type,
              message: msg.event_data?.zone_name ? `INTRUSION: ${msg.event_data.zone_name}` : `ALERT: ${msg.event_type}`,
              timestamp: Date.now()
            });
            setLastAlertTime(Date.now());
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
      // Fetch zones for persistent display
      zonesAPI.getZones(cameraId).then(res => setZones(res)).catch(() => {});
    }
    return () => {
      mountedRef.current = false;
      clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, [connect, cameraId]);

  // Clear alert after 5 seconds
  useEffect(() => {
    if (activeAlert) {
      const timer = setTimeout(() => setActiveAlert(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [activeAlert]);

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

  const resolvedStreamUrl = useMemo(() => {
    if (!streamUrl) return '';
    
    // Handle relative uploads path
    if (streamUrl.startsWith('/uploads')) {
      const protocol = window.location.protocol;
      const hostname = window.location.hostname;
      return encodeURI(`${protocol}//${hostname}:8000${streamUrl}`);
    }

    // Handle absolute file paths that point to the uploads directory
    if (streamUrl.includes('uploads/tactical_archives') || streamUrl.includes('uploads\\tactical_archives')) {
      const parts = streamUrl.split(/[/\\]uploads[/\\]/);
      if (parts.length > 1) {
        const relativePath = `/uploads/${parts[1].replace(/\\/g, '/')}`;
        const protocol = window.location.protocol;
        const hostname = window.location.hostname;
        return encodeURI(`${protocol}//${hostname}:8000${relativePath}`);
      }
    }
    
    return streamUrl;
  }, [streamUrl]);

  const isMjpeg = useMemo(() => isMjpegUrl(resolvedStreamUrl), [resolvedStreamUrl]);

  if (!cameraId) return null;

  const isOnline = cameraStatus === 'online';

  return (
    <div 
      ref={containerRef}
      className={`relative w-full h-full bg-black overflow-hidden select-none ${className}`} 
      id={`camera-player-${cameraId}`}
    >
      
      {/* ── Video Stream ─────────────────────────────────────────── */}
      {isOnline ? (
        <>
          {/* Priority: AI-annotated frame (no lag) → MJPEG → video file */}
          {syncFrame ? (
            <img
              ref={mediaRef}
              src={`data:image/jpeg;base64,${syncFrame}`}
              alt={`Annotated ${cameraName}`}
              className="w-full h-full object-contain"
              onLoad={() => { setIsLoading(false); updateVideoRect(); }}
            />
          ) : isMjpeg ? (
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
                ref={mediaRef}
                src={resolvedStreamUrl}
                alt={`Flux ${cameraName}`}
                className="w-full h-full object-contain"
                onLoad={() => {
                  setIsLoading(false);
                  updateVideoRect();
                }}
                onError={(e) => {
                  console.error('Stream load error:', streamUrl);
                  setImgError(true);
                  setIsLoading(false);
                }}
              />
            )
          ) : (
            <video
              ref={mediaRef}
              src={resolvedStreamUrl}
              autoPlay muted playsInline loop
              className="w-full h-full object-contain"
              onPlaying={() => {
                setIsLoading(false);
                updateVideoRect();
              }}
              onLoadedMetadata={updateVideoRect}
              onError={(e) => {
                setImgError(true);
                setIsLoading(false);
                e.target.style.display = 'none';
              }}
            />
          )}

          {/* ── Zones Overlay (Persistent) ───────────────────────── */}
          {!syncFrame && (
            <div className="absolute pointer-events-none z-10" style={videoRect}>
              <ZoneOverlay zones={zones} />
            </div>
          )}

          {/* ── BBox + MOT Tracking Layer ────────────────────────── */}
          {/* When syncFrame active, boxes are already baked into the annotated image by AI */}
          {showAI && !syncFrame && (
            <div className="absolute pointer-events-none z-20" style={videoRect}>
              <BBoxOverlay detections={detections} zones={zones} showTrajectory={false} showVelocity={false} />
            </div>
          )}

          {/* ── Alert HUD Overlay ────────────────────────────────── */}
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
                    {detections.length > 0 && (
             <div className="flex items-center space-x-2 px-3 py-1 rounded-full bg-cyan-500/10 backdrop-blur-xl border border-cyan-500/20 text-cyan-300">
                <span className="text-[8px] font-black uppercase tracking-[0.2em]">
                   {detections.filter(d => d.track_id != null && d.track_id >= 0).length} TRACKED
                </span>
             </div>
           )}
           <div className="flex items-center space-x-2 px-3 py-1 rounded-full bg-white/5 backdrop-blur-xl border border-white/10 text-neutral-400">
              <span className="text-[8px] font-black uppercase tracking-[0.2em]">
                 {detections.length > 0 ? `${detections.length} DET` : (isMjpeg ? 'MJPEG' : 'STREAM')}
              </span>
           </div>
      </div>
    </div>
  );
};

export default VideoPlayer;
