import React, { useMemo } from 'react';
import CameraCard from './CameraCard.jsx';
import { MonitorOff, Radio } from 'lucide-react';

/**
 * VideoGrid.jsx — Standard surveillance grid
 * Props: cameras[] — list of cameras
 *        layout — '1' | '4' | '9' | '16'
 */
export default function VideoGrid({ cameras = [], layout = '4' }) {
  const visibleCameras = useMemo(() => {
    const count = parseInt(layout);
    return cameras.slice(0, isNaN(count) ? 4 : count);
  }, [cameras, layout]);

  if (cameras.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-32 px-10 gap-6 text-neutral-500 bg-neutral-900/20 rounded-[40px] border border-white/5 border-dashed">
        <div className="relative">
          <MonitorOff size={64} className="opacity-10" />
          <Radio className="absolute -top-2 -right-2 w-6 h-6 text-red-500/20 animate-pulse" />
        </div>
        <div className="text-center">
          <h3 className="text-lg font-black text-white/40 uppercase tracking-widest">Nexus Matrix Offline</h3>
          <p className="text-xs font-medium mt-1">Add cameras in the configuration console to establish a live uplink.</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`video-grid layout-${layout}`} id="video-grid">
      {visibleCameras.map((camera) => (
        <CameraCard key={camera.id} camera={camera} />
      ))}
    </div>
  );
}
