import React, { useState } from 'react';
import { Camera, Grid as GridIcon } from 'lucide-react';
import CameraCard from './CameraCard.jsx';

/**
 * MultiCameraGrid.jsx — Dynamic surveillance matrix
 * Supports 1x1, 2x2, 3x3, 4x4 layouts with fluid animations
 */
const MultiCameraGrid = ({ cameras = [], onCameraSelect, onOpenZoneManager, selectedCameraId, gridLayout: externalGridLayout }) => {
  const [internalGridLayout, setInternalGridLayout] = useState('2x2');
  const [maximizedCameraId, setMaximizedCameraId] = useState(null);
  
  const gridLayout = maximizedCameraId ? '1x1' : (externalGridLayout || internalGridLayout);

  const getGridDimensions = () => {
    const [rows, cols] = gridLayout.split('x').map(Number);
    return { rows, cols };
  };

  const getCameraPosition = (index) => {
    const { cols } = getGridDimensions();
    const row = Math.floor(index / cols);
    const col = index % cols;
    return { row, col };
  };

  const handleToggleMaximize = (camera) => {
    if (maximizedCameraId === camera.id) {
      setMaximizedCameraId(null);
    } else {
      setMaximizedCameraId(camera.id);
    }
  };

  const renderCamera = (camera, index) => {
    const { row, col } = getCameraPosition(index);
    const { rows, cols } = getGridDimensions();
    
    const cellWidth = 100 / cols;
    const cellHeight = 100 / rows;
    
    const isSelected = selectedCameraId === camera.id;
    const isMaximized = maximizedCameraId === camera.id;

    return (
      <div
        key={camera.id}
        className="absolute transition-all duration-200 ease-out p-2"
        style={{
          left: `${col * cellWidth}%`,
          top: `${row * cellHeight}%`,
          width: `${cellWidth}%`,
          height: `${cellHeight}%`,
          zIndex: isSelected ? 10 : 1
        }}
        onClick={(e) => {
          e.stopPropagation();
          onCameraSelect?.(camera);
        }}
      >
        <CameraCard 
          camera={camera} 
          isMaximized={isMaximized}
          onToggleMaximize={handleToggleMaximize}
          onOpenZoneManager={(cam) => onOpenZoneManager?.(cam)}
        />
        
        {/* Selection Glow */}
        {isSelected && !isMaximized && (
          <div className="absolute inset-0 border-2 border-blue-500 rounded-[32px] pointer-events-none shadow-[0_0_30px_rgba(59,130,246,0.4)] z-20 animate-in fade-in zoom-in duration-300 ring-4 ring-blue-500/10" />
        )}
      </div>
    );
  };

  const { rows, cols } = getGridDimensions();
  const maxVisible = rows * cols;
  
  let visibleCameras = [];
  if (Array.isArray(cameras)) {
    if (maximizedCameraId) {
       const cam = cameras.find(c => c.id === maximizedCameraId);
       if (cam) {
         visibleCameras = [cam];
       } else {
         setMaximizedCameraId(null);
       }
    } else if (selectedCameraId) {
       const selectedIndex = cameras.findIndex(c => c.id === selectedCameraId);
       if (selectedIndex !== -1 && selectedIndex >= maxVisible) {
         // Selected camera exists but is outside current view; move it to position 0
         const reordered = [
             cameras[selectedIndex],
             ...cameras.filter((_, idx) => idx !== selectedIndex)
         ];
         visibleCameras = reordered.slice(0, maxVisible);
       } else {
         visibleCameras = cameras.slice(0, maxVisible);
       }
       if (maxVisible === 1) {
           visibleCameras = visibleCameras.slice(0, 1);
       }
    } else {
      visibleCameras = cameras.slice(0, maxVisible);
    }
  }

  return (
    <div className="relative w-full h-full bg-[#0a0a0c] min-h-[400px]">
      {/* Internal Grid Controls (Responsive) */}
      {!externalGridLayout && (
        <div className="absolute top-6 right-6 z-50 flex bg-black/60 backdrop-blur-xl border border-white/10 rounded-2xl p-1 shadow-2xl">
          {['1x1', '2x2', '3x3', '4x4'].map((layout) => (
            <button
              key={layout}
              onClick={(e) => {
                e.stopPropagation();
                setInternalGridLayout(layout);
              }}
              className={`flex items-center space-x-2 px-3 py-1.5 rounded-xl transition-all ${
                internalGridLayout === layout
                  ? 'bg-blue-600 text-white shadow-lg'
                  : 'text-neutral-500 hover:text-white'
              }`}
            >
              <GridIcon className="w-3.5 h-3.5" />
              <span className="text-[10px] font-black">{layout}</span>
            </button>
          ))}
        </div>
      )}

      <div className="relative w-full h-full p-2 transition-all duration-500">
        {visibleCameras.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full space-y-6 animate-in fade-in zoom-in duration-700">
             <div className="relative">
               <div className="absolute inset-0 bg-blue-500/20 blur-3xl rounded-full" />
               <div className="relative p-10 bg-neutral-900 border border-white/5 rounded-full shadow-2xl">
                  <Camera className="w-20 h-20 text-neutral-800" />
               </div>
             </div>
             <div className="text-center">
               <p className="text-lg font-black uppercase tracking-widest text-white/80">No Sensor Link</p>
               <p className="text-xs text-neutral-500 font-medium mt-2 max-w-[240px]">Initialize your tactical nodes in the configuration center to begin surveillance.</p>
             </div>
          </div>
        ) : (
          <div className="relative w-full h-full">
            {visibleCameras.map((camera, index) => renderCamera(camera, index))}
          </div>
        )}
      </div>
    </div>
  );
};

export default MultiCameraGrid;