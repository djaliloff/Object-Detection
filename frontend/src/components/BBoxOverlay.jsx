import React from 'react';

/**
 * BBoxOverlay.jsx — Overlay pour afficher les bounding boxes des détections IA
 * Props: detections[] — [{xmin, ymin, xmax, ymax, label, confidence}]
 * Les coordonnées sont normalisées (0.0 à 1.0)
 */
const BBoxOverlay = ({ detections = [] }) => {
  if (!Array.isArray(detections)) return null;

  return (
    <div className="absolute inset-0 pointer-events-none z-50 overflow-hidden select-none">
      {detections.map((det, idx) => {
        // Support multiple coordinate formats
        const xmin = det.xmin ?? det.bbox?.[0] ?? 0;
        const ymin = det.ymin ?? det.bbox?.[1] ?? 0;
        const xmax = det.xmax ?? det.bbox?.[2] ?? 0;
        const ymax = det.ymax ?? det.bbox?.[3] ?? 0;
        const label = det.label || det.class_name || 'Object';
        const confidence = det.confidence ?? 1.0;

        return (
          <div
            key={`${idx}-${label}`}
            className="absolute border-2 border-blue-500/80 rounded-[4px] shadow-[0_0_15px_rgba(59,130,246,0.3)]"
            style={{
              left: `${xmin * 100}%`,
              top: `${ymin * 100}%`,
              width: `${(xmax - xmin) * 100}%`,
              height: `${(ymax - ymin) * 100}%`,
              transition: 'all 0.15s ease-out'
            }}
          >
            {/* Tactical Label */}
            <div className="absolute top-0 left-0 -translate-y-[calc(100%+2px)] bg-blue-600/90 backdrop-blur-md text-white text-[9px] font-black px-2 py-0.5 rounded-t-sm border-t border-x border-blue-400/50 flex items-center space-x-2 whitespace-nowrap">
              <span className="uppercase tracking-widest">{label}</span>
              <span className="opacity-60 text-[8px]">{Math.round(confidence * 100)}%</span>
            </div>
            
            {/* Corner Accents */}
            <div className="absolute -top-[1px] -left-[1px] w-2 h-2 border-t-2 border-l-2 border-white rounded-tl-[3px]" />
            <div className="absolute -bottom-[1px] -right-[1px] w-2 h-2 border-b-2 border-r-2 border-white rounded-br-[3px]" />
          </div>
        );
      })}
      
      {/* HUD Scanline Effect */}
      {detections.length > 0 && (
        <div className="absolute inset-0 bg-blue-500/5 mix-blend-overlay animate-pulse pointer-events-none" />
      )}
    </div>
  );
};

export default BBoxOverlay;
