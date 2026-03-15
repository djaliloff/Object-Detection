import React, { useMemo } from 'react';

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

const BBoxOverlay = ({ detections = [], showTrajectory = true, showVelocity = true }) => {
  if (!Array.isArray(detections)) return null;

  // Memoize trajectory SVG paths
  const trajectoryPaths = useMemo(() => {
    if (!showTrajectory) return {};
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

        return (
          <div
            key={hasTrackId ? `track-${trackId}` : `det-${idx}`}
            className="absolute rounded-[3px]"
            style={{
              left: `${xmin * 100}%`,
              top: `${ymin * 100}%`,
              width: `${(xmax - xmin) * 100}%`,
              height: `${(ymax - ymin) * 100}%`,
              border: `2px solid ${hexToRgba(color, 0.85)}`,
              boxShadow: `0 0 12px ${hexToRgba(color, 0.25)}, inset 0 0 6px ${hexToRgba(color, 0.08)}`,
              transition: 'all 0.12s ease-out',
            }}
          >
            {/* ─── Track ID Badge ─── */}
            {hasTrackId && (
              <div
                className="absolute -top-[1px] -right-[1px] flex items-center justify-center rounded-bl-md rounded-tr-[2px]"
                style={{
                  background: color,
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
              className="absolute top-0 left-0 -translate-y-[calc(100%+2px)] flex items-center space-x-1.5 whitespace-nowrap rounded-t-sm"
              style={{
                background: hexToRgba(color, 0.88),
                backdropFilter: 'blur(8px)',
                padding: '2px 6px',
                borderTop: `1px solid ${hexToRgba(color, 0.5)}`,
                borderLeft: `1px solid ${hexToRgba(color, 0.5)}`,
                borderRight: `1px solid ${hexToRgba(color, 0.5)}`,
              }}
            >
              <span className="uppercase tracking-widest text-white text-[9px] font-black">
                {det.class_name || label}
              </span>
              <span className="text-white/60 text-[8px] font-semibold">
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
                borderTop: `2.5px solid ${color}`,
                borderLeft: `2.5px solid ${color}`,
              }}
            />
            <div
              className="absolute -bottom-[1px] -right-[1px] w-2.5 h-2.5 rounded-br-[3px]"
              style={{
                borderBottom: `2.5px solid ${color}`,
                borderRight: `2.5px solid ${color}`,
              }}
            />
            <div
              className="absolute -top-[1px] -right-[1px] w-2.5 h-2.5 rounded-tr-[3px]"
              style={{
                borderTop: `2.5px solid ${color}`,
                borderRight: `2.5px solid ${color}`,
              }}
            />
            <div
              className="absolute -bottom-[1px] -left-[1px] w-2.5 h-2.5 rounded-bl-[3px]"
              style={{
                borderBottom: `2.5px solid ${color}`,
                borderLeft: `2.5px solid ${color}`,
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
