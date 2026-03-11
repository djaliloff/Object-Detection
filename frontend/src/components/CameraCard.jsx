import React from 'react';
import { MoreVertical, Maximize2, Activity, Shield, Radio } from 'lucide-react';
import VideoPlayer from './VideoPlayer.jsx';

/**
 * CameraCard.jsx — Individul component for camera feed
 * Combines VideoPlayer with tactical overlays and status info
 */
const CameraCard = ({ camera, onMaximize }) => {
  if (!camera) return null;
  const isOnline = camera.status === 'online';

  return (
    <div className="group relative bg-neutral-900 overflow-hidden rounded-[32px] border border-white/5 flex flex-col h-full shadow-2xl transition-all duration-500 hover:border-blue-500/30 hover:shadow-blue-500/10">
      
      {/* ── Overlay Header ── */}
      <div className="absolute top-0 left-0 right-0 z-20 p-4 flex items-center justify-between bg-gradient-to-b from-black/80 to-transparent pointer-events-none">
        <div className="flex items-center space-x-3 pointer-events-auto">
          <div className={`flex items-center space-x-2 bg-black/40 backdrop-blur-md px-3 py-1.5 rounded-xl border border-white/10 ${isOnline ? 'text-green-400' : 'text-neutral-500'}`}>
            <Radio className={`w-3 h-3 ${isOnline ? 'animate-pulse' : ''}`} />
            <span className="text-[9px] font-black uppercase tracking-widest">{isOnline ? 'Live' : 'No Signal'}</span>
          </div>
          <h3 className="text-sm font-black text-white uppercase tracking-tight drop-shadow-md truncate max-w-[120px]">
            {camera.name}
          </h3>
        </div>
        
        <div className="flex space-x-2 pointer-events-auto opacity-0 group-hover:opacity-100 transition-opacity">
          <button 
            onClick={() => onMaximize?.(camera)}
            className="p-2 bg-white/5 backdrop-blur-md rounded-xl border border-white/10 hover:bg-white/10 text-white transition-all transform hover:scale-110"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
          <button 
            className="p-2 bg-white/5 backdrop-blur-md rounded-xl border border-white/10 hover:bg-white/10 text-white transition-all"
            onClick={(e) => {
              e.stopPropagation();
              import('react-hot-toast').then(({ default: toast }) => {
                toast('Tactical options menu not yet initialized', { icon: '🚧' });
              });
            }}
          >
            <MoreVertical className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* ── Video Content ── */}
      <div className="flex-1 relative min-h-0 bg-neutral-950">
        <VideoPlayer camera={camera} className="w-full h-full" />
      </div>

      {/* ── Footer Stats ── */}
      <div className="p-4 bg-neutral-900/90 backdrop-blur-xl border-t border-white/5 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className="px-2 py-0.5 bg-white/5 rounded-md border border-white/10 text-[8px] font-black text-white/40 uppercase tracking-widest font-mono">
            {camera.config?.resolution || '1080P'}
          </div>
          <div className="h-2 w-px bg-white/10" />
          <div className="flex items-center space-x-1 text-[8px] font-black text-blue-400/80 uppercase tracking-widest">
            <Activity className="w-3 h-3" />
            <span>{camera.config?.fps || '25'} FPS</span>
          </div>
        </div>
        
        <div className="flex items-center space-x-1 text-[8px] font-black text-neutral-500 uppercase tracking-widest italic group-hover:text-neutral-300 transition-colors">
          <Shield className="w-3 h-3 opacity-50" />
          <span>Sector {camera.location || 'Nexus-1'}</span>
        </div>
      </div>
      
      {/* ── Visual Scanning Line (Active State) ── */}
      {isOnline && (
        <div className="absolute inset-0 pointer-events-none opacity-0 group-hover:opacity-10 transition-opacity overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-blue-500 shadow-[0_0_15px_rgba(59,130,246,1)] animate-scan-hud" />
        </div>
      )}

      <style jsx>{`
        @keyframes scan-hud {
          0% { transform: translateY(-100%); }
          100% { transform: translateY(400%); }
        }
        .animate-scan-hud {
          animation: scan-hud 3.5s linear infinite;
        }
      `}</style>
    </div>
  );
};

export default CameraCard;
