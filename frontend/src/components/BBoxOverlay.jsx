import React, { useMemo, useState, useEffect } from 'react';

/**
 * BBoxOverlay.jsx — Multi-Object Tracking overlay with:
 * - Track ID badges with unique per-track colors
 * - Trajectory trails (motion history)
 * - Velocity direction indicators
 * - Confidence display
 * 
 * Props: detections[] — from AI engine with MOT fields:
 *   { bbox, class_name, confidence, track_id, track_color, trajectory, velocity, age, hits }
 * Coordinates are normalized (0.0 to 1.0)
 */

const TRACK_COLORS = [
  '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
  '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
  '#F0B27A', '#82E0AA', '#F1948A', '#AED6F1', '#D7BDE2',
  '#A3E4D7', '#FAD7A0', '#A9CCE3', '#D5DBDB', '#F9E79F',
];

const getTrackColor = (trackId) => {
  if (trackId == null || trackId < 0) return '#3B82F6';
  return TRACK_COLORS[trackId % TRACK_COLORS.length];
};

const hexToRgba = (hex, alpha) => {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
};

const TARGET_CLASSES = ['suitcase', 'handbag', 'backpack'];

function isPointInPolygon(point, vs) {
  let x = point[0], y = point[1];
  let inside = false;
  for (let i = 0, j = vs.length - 1; i < vs.length; j = i++) {
    let xi = vs[i][0], yi = vs[i][1];
    let xj = vs[j][0], yj = vs[j][1];
    let intersect = ((yi > y) != (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
}

function checkZoneIntrusion(xmin, ymin, xmax, ymax, zones) {
  if (!zones || zones.length === 0) return false;
  const xCenter = (xmin + xmax) / 2;
  const yBottom = ymax;
  const point = [xCenter, yBottom];

  for (const zone of zones) {
    if (zone.zone_type !== 'exclusion' || !zone.is_active) continue;
    const config = zone.config_json || {};
    if (config.shape === 'polygon' && zone.polygon) {
      if (isPointInPolygon(point, zone.polygon)) return true;
    } else if ((config.shape === 'square' || config.shape === 'rectangle') && config.rect) {
      const [zx, zy, zw, zh] = config.rect;
      if (xCenter >= zx && xCenter <= zx + zw && yBottom >= zy && yBottom <= zy + zh) return true;
    } else if (config.shape === 'circle' && config.center && config.radius) {
      const [cx, cy] = config.center;
      const r = config.radius;
      if (Math.pow(xCenter - cx, 2) + Math.pow(yBottom - cy, 2) <= r * r) return true;
    }
  }
  return false;
}

const BBoxOverlay = ({ detections = [], zones = [], showTrajectory = true, showVelocity = true }) => {
  const [staticObjects, setStaticObjects] = useState([]);
  // Derive `now` at render time — no setInterval needed, avoids forced re-renders every second
  const now = Date.now();

  useEffect(() => {
    if (!Array.isArray(detections)) return;
    
    const nowTime = Date.now();
    
    setStaticObjects(prev => {
      let updated = [...prev];
      
      detections.forEach(det => {
        const className = (det.class_name || det.label || '').toLowerCase().trim();
        if (TARGET_CLASSES.includes(className)) {
          const detBBox = det.bbox || [det.xmin, det.ymin, det.xmax, det.ymax];
          if (!detBBox) return;
          
          const [x1, y1, x2, y2] = detBBox;
          const cx = (x1 + x2) / 2;
          const cy = (y1 + y2) / 2;
          
          let matched = false;
          for (let obj of updated) {
            const [ox1, oy1, ox2, oy2] = obj.bbox;
            const ocx = (ox1 + ox2) / 2;
            const ocy = (oy1 + oy2) / 2;
            
            // Allow ~10% screen movement for matching static objects
            const dist = Math.sqrt(Math.pow(cx - ocx, 2) + Math.pow(cy - ocy, 2));
            if (dist < 0.1 && obj.class_name === className) {
              obj.lastSeen = nowTime;
              obj.bbox = detBBox;
              det._spatialId = obj.id;
              matched = true;
              break;
            }
          }
          
          if (!matched) {
            const newId = `static-${Math.random().toString(36).substr(2, 9)}`;
            updated.push({
              id: newId,
              class_name: className,
              bbox: detBBox,
              firstSeen: nowTime,
              lastSeen: nowTime
            });
            det._spatialId = newId;
          }
        }
      });
      
      // Cleanup objects not seen for > 5 seconds to avoid memory leaks or ghost alerts
      return updated.filter(obj => nowTime - obj.lastSeen < 5000);
    });
  }, [detections]);

  // Memoize trajectory SVG paths
  const trajectoryPaths = useMemo(() => {
    if (!showTrajectory || !Array.isArray(detections)) return {};
    const paths = {};
    detections.forEach((det) => {
      const trajectory = det.trajectory;
      if (!trajectory || trajectory.length < 2) return;
      const trackId = det.track_id;
      if (trackId == null) return;

      // Build SVG path
      const points = trajectory.map(([x, y]) => `${x * 100}% ${y * 100}%`);
      paths[trackId] = {
        points: trajectory,
        color: det.track_color || getTrackColor(trackId),
      };
    });
    return paths;
  }, [detections, showTrajectory]);

  if (!Array.isArray(detections)) return null;

  return (
    <div className="absolute inset-0 pointer-events-none z-50 overflow-hidden select-none">
      {/* ─── Trajectory Trails (SVG) ─── */}
      {showTrajectory && (
        <svg
          className="absolute inset-0 w-full h-full"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          style={{ overflow: 'visible' }}
        >
          <defs>
            {Object.entries(trajectoryPaths).map(([trackId, { color }]) => (
              <linearGradient
                key={`grad-${trackId}`}
                id={`trail-grad-${trackId}`}
                x1="0%" y1="0%" x2="100%" y2="0%"
              >
                <stop offset="0%" stopColor={color} stopOpacity="0" />
                <stop offset="100%" stopColor={color} stopOpacity="0.8" />
              </linearGradient>
            ))}
          </defs>
          {Object.entries(trajectoryPaths).map(([trackId, { points, color }]) => {
            if (points.length < 2) return null;
            const pathData = points
              .map(([x, y], i) => `${i === 0 ? 'M' : 'L'} ${x * 100} ${y * 100}`)
              .join(' ');

            return (
              <g key={`trail-${trackId}`}>
                {/* Glow effect */}
                <path
                  d={pathData}
                  fill="none"
                  stroke={hexToRgba(color, 0.15)}
                  strokeWidth="0.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                {/* Main trail line */}
                <path
                  d={pathData}
                  fill="none"
                  stroke={`url(#trail-grad-${trackId})`}
                  strokeWidth="0.25"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                {/* Current position dot */}
                {points.length > 0 && (
                  <circle
                    cx={points[points.length - 1][0] * 100}
                    cy={points[points.length - 1][1] * 100}
                    r="0.35"
                    fill={color}
                    opacity="0.9"
                  >
                    <animate
                      attributeName="r"
                      values="0.25;0.45;0.25"
                      dur="1.5s"
                      repeatCount="indefinite"
                    />
                  </circle>
                )}
              </g>
            );
          })}
        </svg>
      )}

      {/* ─── Bounding Boxes + Track Labels ─── */}
      {detections.map((det, idx) => {
        const xmin = det.xmin ?? det.bbox?.[0] ?? 0;
        const ymin = det.ymin ?? det.bbox?.[1] ?? 0;
        const xmax = det.xmax ?? det.bbox?.[2] ?? 0;
        const ymax = det.ymax ?? det.bbox?.[3] ?? 0;
        const label = det.label || det.class_name || 'Object';
        const confidence = det.confidence ?? 1.0;
        const trackId = det.track_id;
        const color = det.track_color || det.color || getTrackColor(trackId);
        const hasTrackId = trackId != null && trackId >= 0;
        const velocity = det.velocity;

        const classNameLower = (det.class_name || det.label || '').toLowerCase().trim();
        const isTarget = TARGET_CLASSES.includes(classNameLower);
        const isPerson = classNameLower === 'person';
        const isIntruding = isPerson && checkZoneIntrusion(xmin, ymin, xmax, ymax, zones);
        
        const finalColor = isIntruding ? '#ef4444' : color;
        
        let durationSec = 0;
        let isMissingAlert = false;
        let startTime = null;
        
        if (isTarget && det._spatialId) {
          const staticObj = staticObjects.find(o => o.id === det._spatialId);
          if (staticObj) {
            startTime = staticObj.firstSeen;
            durationSec = Math.floor((now - startTime) / 1000);
            if (durationSec >= 180) {
               isMissingAlert = true;
            }
          }
        }

        return (
          <div
            key={hasTrackId ? `track-${trackId}` : `det-${idx}`}
            className={`absolute rounded-[4px] detection-box-premium ${isIntruding ? 'animate-pulse' : ''}`}
            style={{
              left: `${xmin * 100}%`,
              top: `${ymin * 100}%`,
              width: `${(xmax - xmin) * 100}%`,
              height: `${(ymax - ymin) * 100}%`,
              border: `4px solid ${hexToRgba(finalColor, isIntruding ? 1.0 : 0.8)}`,
              boxShadow: `0 0 20px ${hexToRgba(finalColor, 0.6)}, inset 0 0 10px ${hexToRgba(finalColor, 0.25)}`,
              transition: 'all 0.1s cubic-bezier(0.17, 0.67, 0.83, 0.67)',
              background: `${hexToRgba(finalColor, isIntruding ? 0.2 : 0.05)}`,
            }}
          >
            {/* ─── Target Object Counter / Alert ─── */}
            {isTarget && startTime && (
              <div 
                className={`absolute left-1/2 -translate-x-1/2 whitespace-nowrap px-2 py-1 rounded-md text-[10px] font-black tracking-widest shadow-xl z-20 transition-all duration-300 ${isMissingAlert ? 'bg-yellow-400 text-black animate-pulse scale-110' : 'bg-black/80 text-white backdrop-blur-md'}`}
                style={{
                  top: '-35px',
                  border: `2px solid ${isMissingAlert ? '#fbbf24' : 'rgba(255,255,255,0.2)'}`,
                }}
              >
                {isMissingAlert ? 'MISSING OBJECT' : `${durationSec}S`}
              </div>
            )}

            {/* ─── Track ID Badge ─── */}
            {hasTrackId && (
              <div
                className="absolute -top-[2px] -right-[2px] flex items-center justify-center rounded-bl-md rounded-tr-[2px]"
                style={{
                  background: finalColor,
                  minWidth: '20px',
                  height: '16px',
                  padding: '0 4px',
                }}
              >
                <span className="text-[9px] font-black text-white tracking-wide leading-none">
                  #{trackId}
                </span>
              </div>
            )}

            {/* ─── Label Bar ─── */}
            <div
              className={`absolute top-0 left-0 -translate-y-[calc(100%+2px)] flex items-center space-x-1.5 whitespace-nowrap rounded-t-sm ${isIntruding ? 'animate-bounce' : ''}`}
              style={{
                background: hexToRgba(finalColor, 0.95),
                backdropFilter: 'blur(12px)',
                padding: '3px 8px',
                borderTop: `1px solid ${hexToRgba(finalColor, 0.6)}`,
                borderLeft: `1px solid ${hexToRgba(finalColor, 0.6)}`,
                borderRight: `1px solid ${hexToRgba(finalColor, 0.6)}`,
                boxShadow: isIntruding ? `0 -4px 12px ${hexToRgba(finalColor, 0.4)}` : 'none',
              }}
            >
              <span className="uppercase tracking-widest text-white text-[9px] font-black">
                {det.class_name || label} {isIntruding ? ' [INTRUSION]' : ''}
              </span>
              <span className="text-white/80 text-[8px] font-bold">
                {Math.round(confidence * 100)}%
              </span>
              {/* Velocity indicator */}
              {showVelocity && velocity && (velocity.vx !== 0 || velocity.vy !== 0) && (
                <span
                  className="text-[8px] font-bold"
                  style={{ 
                    color: hexToRgba('#FFFFFF', 0.7),
                    transform: `rotate(${Math.atan2(velocity.vy, velocity.vx) * (180 / Math.PI)}deg)`,
                    display: 'inline-block',
                  }}
                >
                  →
                </span>
              )}
            </div>

            {/* ─── Corner Accents ─── */}
            <div
              className="absolute -top-[1px] -left-[1px] w-2.5 h-2.5 rounded-tl-[3px]"
              style={{
                borderTop: `3.5px solid ${finalColor}`,
                borderLeft: `3.5px solid ${finalColor}`,
              }}
            />
            <div
              className="absolute -bottom-[1px] -right-[1px] w-2.5 h-2.5 rounded-br-[3px]"
              style={{
                borderBottom: `3.5px solid ${finalColor}`,
                borderRight: `3.5px solid ${finalColor}`,
              }}
            />
            <div
              className="absolute -top-[1px] -right-[1px] w-2.5 h-2.5 rounded-tr-[3px]"
              style={{
                borderTop: `3.5px solid ${finalColor}`,
                borderRight: `3.5px solid ${finalColor}`,
              }}
            />
            <div
              className="absolute -bottom-[1px] -left-[1px] w-2.5 h-2.5 rounded-bl-[3px]"
              style={{
                borderBottom: `3.5px solid ${finalColor}`,
                borderLeft: `3.5px solid ${finalColor}`,
              }}
            />
          </div>
        );
      })}

      {/* ─── HUD Stats Overlay (bottom-left) ─── */}
      {detections.length > 0 && (
        <div
          className="absolute bottom-2 left-2 flex items-center space-x-2"
          style={{
            background: 'rgba(0,0,0,0.65)',
            backdropFilter: 'blur(6px)',
            borderRadius: '6px',
            padding: '4px 8px',
            border: '1px solid rgba(255,255,255,0.08)',
          }}
        >
          <div className="flex items-center space-x-1">
            <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            <span className="text-[9px] text-white/80 font-semibold tracking-wide">
              {detections.length} DETECTIONS
            </span>
          </div>
          <div className="w-px h-3 bg-white/20" />
          <span className="text-[9px] text-cyan-300/80 font-semibold tracking-wide">
            {detections.filter(d => d.track_id != null && d.track_id >= 0).length} TRACKED
          </span>
        </div>
      )}

      {/* ─── Subtle scan effect ─── */}
      {detections.length > 0 && (
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: 'linear-gradient(180deg, transparent 0%, rgba(59,130,246,0.02) 50%, transparent 100%)',
            animation: 'scan 3s ease-in-out infinite',
          }}
        />
      )}

      <style>{`
        @keyframes scan {
          0%, 100% { transform: translateY(-100%); }
          50% { transform: translateY(100%); }
        }
      `}</style>
    </div>
  );
};

export default BBoxOverlay;