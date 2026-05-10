import React, { useState } from 'react';
import { 
  Camera, 
  Maximize2, 
  Minimize2, 
  Volume2, 
  VolumeX, 
  Circle,
  Aperture,
  ZoomIn,
  ZoomOut,
  Settings,
  Download,
  Share2,
  Play,
  Pause,
  ChevronUp,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Crosshair
} from 'lucide-react';
import toast from 'react-hot-toast';

const CameraControls = ({ 
  camera, 
  isRecording = false, 
  isStreaming = true,
  isFullscreen = false,
  onToggleRecording,
  onToggleStream,
  onToggleFullscreen,
  onTakeSnapshot,
  onPTZControl,
  onZoomControl,
  onOpenSettings,
  className = ""
}) => {
  const [isMuted, setIsMuted] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(100);

  const handleSnapshot = () => {
    onTakeSnapshot?.();
    toast.success('Intelligence snapshot captured');
  };

  const handleRecording = () => {
    onToggleRecording?.();
    toast.success(isRecording ? 'Surveillance feed archive closed' : 'Surveillance feed archive active');
  };

  const handleStreamToggle = () => {
    onToggleStream?.();
    toast(isStreaming ? 'Stream execution paused' : 'Stream execution resumed');
  };

  const handleMuteToggle = () => {
    setIsMuted(!isMuted);
    toast(!isMuted ? 'Audio feed suppressed' : 'Audio feed restored');
  };

  const handleZoom = (direction) => {
    const newZoom = direction === 'in' 
      ? Math.min(zoomLevel + 25, 200) 
      : Math.max(zoomLevel - 25, 50);
    setZoomLevel(newZoom);
    onZoomControl?.(newZoom);
  };

  const handlePTZ = (direction) => {
    onPTZControl?.(direction);
  };

  if (!camera) return null;

  return (
    <div className={`bg-neutral-900/60 backdrop-blur-3xl border border-white/5 rounded-[32px] p-6 shadow-2xl ${className}`}>
      {/* Header Info */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center space-x-4">
          <div className="p-3 bg-blue-600/20 rounded-2xl border border-blue-500/20">
             <Camera className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <h3 className="text-white font-black uppercase tracking-tight text-lg">{camera.name}</h3>
            <div className="flex items-center space-x-2">
              <span className={`w-2 h-2 rounded-full ${camera.status === 'online' ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
              <span className="text-neutral-500 text-[10px] font-black uppercase tracking-widest">
                {camera.status === 'online' ? 'Active Nexus' : 'Link Severed'}
              </span>
            </div>
          </div>
        </div>
        
        <button
          onClick={onOpenSettings}
          className="p-3 bg-white/5 rounded-2xl text-neutral-400 hover:text-white hover:bg-white/10 transition-all border border-white/5"
        >
          <Settings className="w-5 h-5" />
        </button>
      </div>

      {/* Control Matrix */}
      <div className="space-y-6">
        {/* Core Actions */}
        <div className="grid grid-cols-5 gap-3">
          <button
            onClick={handleRecording}
            className={`flex flex-col items-center justify-center p-4 rounded-2xl border transition-all ${
              isRecording 
                ? 'bg-red-500/20 border-red-500/50 text-red-400 shadow-lg shadow-red-500/10' 
                : 'bg-white/5 border-white/5 text-neutral-400 hover:text-white hover:bg-white/10'
            }`}
          >
            <Circle className={`w-5 h-5 mb-2 ${isRecording ? 'animate-pulse' : ''}`} fill={isRecording ? 'currentColor' : 'none'} />
            <span className="text-[9px] font-black uppercase">Rec</span>
          </button>

          <button
            onClick={handleStreamToggle}
            className={`flex flex-col items-center justify-center p-4 rounded-2xl border transition-all ${
              isStreaming 
                ? 'bg-blue-500/20 border-blue-500/50 text-blue-400' 
                : 'bg-white/5 border-white/5 text-neutral-400 hover:text-white hover:bg-white/10'
            }`}
          >
            {isStreaming ? <Pause className="w-5 h-5 mb-2" /> : <Play className="w-5 h-5 mb-2" />}
            <span className="text-[9px] font-black uppercase">{isStreaming ? 'Pause' : 'Live'}</span>
          </button>

          <button
            onClick={handleSnapshot}
            className="flex flex-col items-center justify-center p-4 bg-white/5 border border-white/5 text-neutral-400 hover:text-white hover:bg-white/10 rounded-2xl transition-all"
          >
            <Aperture className="w-5 h-5 mb-2" />
            <span className="text-[9px] font-black uppercase">Snap</span>
          </button>

          <button
            onClick={handleMuteToggle}
            className="flex flex-col items-center justify-center p-4 bg-white/5 border border-white/5 text-neutral-400 hover:text-white hover:bg-white/10 rounded-2xl transition-all"
          >
            {isMuted ? <VolumeX className="w-5 h-5 mb-2" /> : <Volume2 className="w-5 h-5 mb-2" />}
            <span className="text-[9px] font-black uppercase">Audio</span>
          </button>

          <button
            onClick={onToggleFullscreen}
            className="flex flex-col items-center justify-center p-4 bg-white/5 border border-white/5 text-neutral-400 hover:text-white hover:bg-white/10 rounded-2xl transition-all"
          >
            {isFullscreen ? <Minimize2 className="w-5 h-5 mb-2" /> : <Maximize2 className="w-5 h-5 mb-2" />}
            <span className="text-[9px] font-black uppercase">Zoom</span>
          </button>
        </div>

        {/* PTZ Console */}
        <div className="bg-neutral-800/40 border border-white/5 rounded-[32px] p-6">
           <div className="flex items-center justify-between mb-6">
              <span className="text-[10px] font-black uppercase tracking-widest text-neutral-500">PTZ Telemetry</span>
              <div className="flex space-x-2">
                 <button onClick={() => handleZoom('out')} className="p-2 bg-white/5 rounded-xl border border-white/5 text-neutral-400 hover:text-white transition-all"><ZoomOut className="w-4 h-4" /></button>
                 <button onClick={() => handleZoom('in')} className="p-2 bg-white/5 rounded-xl border border-white/5 text-neutral-400 hover:text-white transition-all"><ZoomIn className="w-4 h-4" /></button>
              </div>
           </div>

           <div className="flex justify-center items-center">
              <div className="relative w-48 h-48 bg-neutral-900 rounded-full border border-white/5 flex items-center justify-center shadow-inner">
                 <div className="absolute inset-4 rounded-full border border-blue-500/10 pointer-events-none" />
                 
                 <button 
                  onClick={() => handlePTZ('up')}
                  className="absolute top-2 p-3 text-neutral-600 hover:text-blue-500 transition-colors"
                 >
                  <ChevronUp className="w-6 h-6" />
                 </button>
                 
                 <button 
                  onClick={() => handlePTZ('down')}
                  className="absolute bottom-2 p-3 text-neutral-600 hover:text-blue-500 transition-colors"
                 >
                  <ChevronDown className="w-6 h-6" />
                 </button>
                 
                 <button 
                  onClick={() => handlePTZ('left')}
                  className="absolute left-2 p-3 text-neutral-600 hover:text-blue-500 transition-colors"
                 >
                  <ChevronLeft className="w-6 h-6" />
                 </button>
                 
                 <button 
                  onClick={() => handlePTZ('right')}
                  className="absolute right-2 p-3 text-neutral-600 hover:text-blue-500 transition-colors"
                 >
                  <ChevronRight className="w-6 h-6" />
                 </button>

                 <button 
                  onClick={() => handlePTZ('home')}
                  className="p-6 bg-blue-600/10 rounded-full border border-blue-500/20 text-blue-500 hover:bg-blue-600/20 transition-all hover:scale-110 active:scale-95 shadow-lg shadow-blue-500/5 group"
                 >
                   <Crosshair className="w-8 h-8 group-hover:rotate-90 transition-transform duration-500" />
                 </button>
              </div>
           </div>
        </div>

        {/* Metadata Footer */}
        <div className="flex items-center justify-between py-2 border-t border-white/5 px-2 mt-4">
           <div className="flex space-x-6">
              <div>
                <p className="text-[8px] font-black uppercase text-neutral-600 mb-1">Optics</p>
                <p className="text-[10px] font-black text-neutral-300 tracking-wider">RAW_{camera.resolution?.replace('x', '_')}</p>
              </div>
              <div>
                <p className="text-[8px] font-black uppercase text-neutral-600 mb-1">Frequency</p>
                <p className="text-[10px] font-black text-neutral-300 tracking-wider">{camera.fps} FPS</p>
              </div>
           </div>
           
           <div className="flex space-x-3">
              <button className="p-2 text-neutral-600 hover:text-white transition-colors"><Download className="w-4 h-4" /></button>
              <button className="p-2 text-neutral-600 hover:text-white transition-colors"><Share2 className="w-4 h-4" /></button>
           </div>
        </div>
      </div>
    </div>
  );
};

export default CameraControls;
