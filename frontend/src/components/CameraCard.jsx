import React, { useState, useRef, useEffect } from 'react';
import { 
  MoreVertical, 
  Maximize2, 
  Activity, 
  Shield, 
  Radio, 
  Eye, 
  EyeOff, 
  Thermometer, 
  Camera as CameraIcon, 
  Settings,
  RefreshCw,
  Zap,
  Info
} from 'lucide-react';
import VideoPlayer from './VideoPlayer.jsx';
import { camerasAPI } from '../utils/api';
import toast from 'react-hot-toast';

const CameraCard = ({ camera, onMaximize, onOpenZoneManager }) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [showAI, setShowAI] = useState(true);
  const menuRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setIsMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  if (!camera) return null;
  const isOnline = camera.status === 'online';

  const handleModalityToggle = async () => {
    const newModality = camera.modality === 'rgb' ? 'thermal' : 'rgb';
    try {
      await camerasAPI.updateCamera(camera.id, { modality: newModality });
      toast.success(`Switching to ${newModality.toUpperCase()} spectrum`, {
        style: { background: '#171717', color: '#fff', border: '1px solid #262626' }
      });
      setIsMenuOpen(false);
    } catch (err) {
      toast.error('Spectrum shift failed');
    }
  };

  const handleSnapshot = () => {
    toast.success('Tactical snapshot captured', {
      icon: '📸',
      style: { background: '#171717', color: '#fff', border: '1px solid #262626' }
    });
    setIsMenuOpen(false);
  };

  return (
    <div className="group relative bg-neutral-900 overflow-hidden rounded-[32px] border border-white/5 flex flex-col h-full shadow-2xl transition-all duration-500 hover:border-blue-500/30 hover:shadow-blue-500/10">
      
      {/* ── Overlay Header ── */}
      <div className="absolute top-0 left-0 right-0 z-40 p-4 flex items-center justify-between bg-gradient-to-b from-black/80 to-transparent pointer-events-none">
        <div className="flex items-center space-x-3 pointer-events-auto">
          <div className={`flex items-center space-x-2 bg-black/40 backdrop-blur-md px-3 py-1.5 rounded-xl border border-white/10 ${isOnline ? 'text-green-400' : 'text-neutral-500'}`}>
            <Radio className={`w-3 h-3 ${isOnline ? 'animate-pulse' : ''}`} />
            <span className="text-[9px] font-black uppercase tracking-widest">{isOnline ? 'Live' : 'No Signal'}</span>
          </div>
          <div className="flex flex-col">
            <h3 className="text-sm font-black text-white uppercase tracking-tight drop-shadow-md truncate max-w-[120px]">
              {camera.name}
            </h3>
            <span className="text-[8px] font-bold text-blue-400/60 uppercase tracking-widest">{camera.modality || 'RGB'} Spectrum</span>
          </div>
        </div>
        
        <div className="flex space-x-2 pointer-events-auto opacity-0 group-hover:opacity-100 transition-opacity">
          <button 
            onClick={() => onMaximize?.(camera)}
            className="p-2 bg-white/5 backdrop-blur-md rounded-xl border border-white/10 hover:bg-white/10 text-white transition-all transform hover:scale-110"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
          
          <div className="relative" ref={menuRef}>
            <button 
              className={`p-2 rounded-xl border transition-all ${
                isMenuOpen 
                  ? 'bg-blue-600 border-blue-500 text-white shadow-[0_0_15px_rgba(59,130,246,0.5)]' 
                  : 'bg-white/5 backdrop-blur-md border-white/10 hover:bg-white/10 text-white'
              }`}
              onClick={(e) => {
                e.stopPropagation();
                setIsMenuOpen(!isMenuOpen);
              }}
            >
              <MoreVertical className="w-4 h-4" />
            </button>

            {/* Tactical Dropdown Menu */}
            {isMenuOpen && (
              <div className="absolute right-0 mt-2 w-56 bg-[#121214]/95 backdrop-blur-2xl border border-white/10 rounded-2xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] overflow-hidden z-50 animate-in fade-in slide-in-from-top-2 duration-200">
                <div className="p-2 space-y-1">
                  <div className="px-3 py-2 mb-1 border-b border-white/5">
                    <p className="text-[10px] font-black text-neutral-500 uppercase tracking-widest">Tactical Options</p>
                  </div>
                  
                  <button 
                    onClick={handleModalityToggle}
                    className="w-full flex items-center justify-between px-3 py-2.5 rounded-xl hover:bg-white/5 text-left transition-colors group/item"
                  >
                    <div className="flex items-center space-x-3">
                      <Thermometer className="w-4 h-4 text-orange-400" />
                      <span className="text-xs font-bold text-neutral-200">Switch Modality</span>
                    </div>
                    <Zap className="w-3 h-3 text-neutral-600 group-hover/item:text-blue-400" />
                  </button>

                  <button 
                    onClick={() => { setShowAI(!showAI); setIsMenuOpen(false); }}
                    className="w-full flex items-center justify-between px-3 py-2.5 rounded-xl hover:bg-white/5 text-left transition-colors"
                  >
                    <div className="flex items-center space-x-3">
                      {showAI ? <EyeOff className="w-4 h-4 text-red-400" /> : <Eye className="w-4 h-4 text-green-400" />}
                      <span className="text-xs font-bold text-neutral-200">{showAI ? 'Hide AI Overlay' : 'Show AI Overlay'}</span>
                    </div>
                  </button>

                  <button 
                    onClick={handleSnapshot}
                    className="w-full flex items-center space-x-3 px-3 py-2.5 rounded-xl hover:bg-white/5 text-left transition-colors"
                  >
                    <CameraIcon className="w-4 h-4 text-blue-400" />
                    <span className="text-xs font-bold text-neutral-200">Capture Snapshot</span>
                  </button>

                  <div className="h-px bg-white/5 my-1" />

                  <button 
                    onClick={() => { setIsMenuOpen(false); onOpenZoneManager?.(camera); }}
                    className="w-full flex items-center space-x-3 px-3 py-2.5 rounded-xl hover:bg-white/5 text-left transition-colors"
                  >
                    <Shield className="w-4 h-4 text-red-500" />
                    <span className="text-xs font-bold text-neutral-200">Restricted Zones</span>
                  </button>

                  <div className="h-px bg-white/5 my-1" />

                  <button 
                    onClick={() => { setIsMenuOpen(false); toast.loading('Re-initializing sensor link...'); }}
                    className="w-full flex items-center space-x-3 px-3 py-2.5 rounded-xl hover:bg-white/5 text-left transition-colors"
                  >
                    <RefreshCw className="w-4 h-4 text-neutral-400" />
                    <span className="text-xs font-bold text-neutral-200">Re-initialize Link</span>
                  </button>

                  <button 
                    className="w-full flex items-center space-x-3 px-3 py-2.5 rounded-xl hover:bg-white/5 text-left transition-colors opacity-50 cursor-not-allowed"
                  >
                    <Settings className="w-4 h-4 text-neutral-400" />
                    <span className="text-xs font-bold text-neutral-200">Sensor Config</span>
                  </button>
                </div>
                <div className="bg-white/5 p-3 flex items-center space-x-2">
                  <Info className="w-3.5 h-3.5 text-blue-400" />
                  <p className="text-[9px] font-medium text-neutral-400 italic">Advanced Neural Analysis Active</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Video Content ── */}
      <div className="flex-1 relative min-h-0 bg-neutral-950">
        <VideoPlayer camera={camera} showAI={showAI} className="w-full h-full" />
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
