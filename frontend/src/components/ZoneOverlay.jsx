import React, { useMemo } from 'react';

/**
 * ZoneOverlay.jsx — Persistent rendering of tactical zones on the video player.
 * Supports Polygon, Circle, and Rect shapes with tactical styling.
 */

const ZoneOverlay = ({ zones = [], videoRect = {} }) => {
  if (!zones || zones.length === 0) return null;

  return (
    <svg
      className="absolute inset-0 w-full h-full pointer-events-none z-10"
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      style={{ overflow: 'visible' }}
    >
      <defs>
        <filter id="zone-glow">
          <feGaussianBlur stdDeviation="0.5" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
        
        {/* Animated scanline pattern */}
        <pattern id="scanline-pattern" width="1" height="0.1" patternUnits="userSpaceOnUse">
          <line x1="0" y1="0" x2="1" y2="0" stroke="rgba(255,255,255,0.05)" strokeWidth="0.05" />
        </pattern>
      </defs>

      {zones.map((zone) => {
        const config = zone.config_json || {};
        const isExclusion = zone.zone_type === 'exclusion';
        const color = isExclusion ? '#ef4444' : '#3b82f6';
        const isActive = zone.is_active;

        if (!isActive) return null;

        let pathData = '';
        if (config.shape === 'polygon' && zone.polygon) {
          pathData = zone.polygon
            .map((pt, i) => `${i === 0 ? 'M' : 'L'} ${pt[0] * 100} ${pt[1] * 100}`)
            .join(' ') + ' Z';
        } else if (config.shape === 'circle' && config.center) {
          // Approximate circle with path or just use <circle>
          // We'll use <circle> below
        } else if ((config.shape === 'square' || config.shape === 'rectangle') && config.rect) {
          const [x, y, w, h] = config.rect;
          pathData = `M ${x * 100} ${y * 100} L ${(x + w) * 100} ${y * 100} L ${(x + w) * 100} ${(y + h) * 100} L ${x * 100} ${(y + h) * 100} Z`;
        }

        return (
          <g key={zone.id} className="zone-group">
            {/* Main Shape */}
            {config.shape === 'circle' ? (
              <circle
                cx={config.center[0] * 100}
                cy={config.center[1] * 100}
                r={config.radius * 100}
                fill={isExclusion ? 'rgba(239, 68, 68, 0.05)' : 'rgba(59, 130, 246, 0.05)'}
                stroke={color}
                strokeWidth="0.5"
                strokeDasharray={isExclusion ? "1 1" : "none"}
                filter="url(#zone-glow)"
                className={isExclusion ? "animate-pulse" : ""}
                style={{ transition: 'all 0.3s ease' }}
              />
            ) : (
              <path
                d={pathData}
                fill={isExclusion ? 'rgba(239, 68, 68, 0.05)' : 'rgba(59, 130, 246, 0.05)'}
                stroke={color}
                strokeWidth="0.5"
                strokeDasharray={isExclusion ? "1 1" : "none"}
                filter="url(#zone-glow)"
                className={isExclusion ? "animate-pulse" : ""}
                style={{ transition: 'all 0.3s ease' }}
              />
            )}

            {/* Tactical Label HUD */}
            <g transform={`translate(${
              (config.shape === 'circle' ? config.center[0] : (config.rect ? config.rect[0] : (zone.polygon ? zone.polygon[0][0] : 0))) * 100
            }, ${
              (config.shape === 'circle' ? config.center[1] : (config.rect ? config.rect[1] : (zone.polygon ? zone.polygon[0][1] : 0))) * 100 - 2
            })`}>
              <rect
                x="-1"
                y="-3"
                width={zone.name.length * 1.5 + 4}
                height="4"
                fill="rgba(0,0,0,0.7)"
                rx="0.5"
              />
              <text
                x="1"
                y="0"
                fill={color}
                fontSize="2"
                fontWeight="900"
                className="uppercase tracking-tighter"
              >
                {zone.name}
              </text>
              <line x1="0" y1="-3" x2="0" y2="1" stroke={color} strokeWidth="0.2" />
            </g>
          </g>
        );
      })}
    </svg>
  );
};

export default ZoneOverlay;
