import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { 
  X, 
  Save, 
  Trash2, 
  Square, 
  Circle, 
  MousePointer2, 
  Eye, 
  EyeOff,
  Plus,
  ShieldAlert,
  Target
} from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { zonesAPI } from '../utils/api';
import toast from 'react-hot-toast';

const isMjpegUrl = (url = '') => {
  if (!url) return false;
  const u = url.toLowerCase();
  // If it's a known video/streaming extension, it's NOT MJPEG
  if (u.endsWith('.mp4') || u.endsWith('.mkv') || u.endsWith('.avi') || u.endsWith('.webm') || u.endsWith('.m3u8')) {
    return false;
  }
  return u.includes('/video') || u.includes('/mjpeg') || u.includes('/stream') || (u.startsWith('http') && !u.includes('.mp4'));
};

const ZoneManagerModal = ({ isOpen, onClose, camera }) => {
  const queryClient = useQueryClient();
  const canvasRef = useRef(null);
  const [drawingMode, setDrawingMode] = useState('none'); // none, square, circle
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPos, setStartPos] = useState(null);
  const [currentPos, setCurrentPos] = useState(null);
  const [isMediaLoading, setIsMediaLoading] = useState(true);

  const streamUrl = useMemo(() => {
    const url = camera?.stream_url || camera?.mjpeg_url || camera?.hls_url || camera?.rtsp_url;
    if (!url) return '';
    
    // Handle relative uploads path
    if (url.startsWith('/uploads')) {
      const protocol = window.location.protocol;
      const hostname = window.location.hostname;
      return encodeURI(`${protocol}//${hostname}:8000${url}`);
    }

    // Handle absolute file paths that point to the uploads directory
    if (url.includes('uploads/tactical_archives') || url.includes('uploads\\tactical_archives')) {
      const parts = url.split(/[/\\]uploads[/\\]/);
      if (parts.length > 1) {
        const relativePath = `/uploads/${parts[1].replace(/\\/g, '/')}`;
        const protocol = window.location.protocol;
        const hostname = window.location.hostname;
        return encodeURI(`${protocol}//${hostname}:8000${relativePath}`);
      }
    }

    return url;
  }, [camera]);

  const isMjpeg = useMemo(() => isMjpegUrl(streamUrl), [streamUrl]);

  const { data: zones = [], isLoading } = useQuery({
    queryKey: ['zones', camera?.id],
    queryFn: () => zonesAPI.getZones(camera?.id),
    enabled: !!camera?.id && isOpen,
  });

  const createZoneMutation = useMutation({
    mutationFn: zonesAPI.createZone,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['zones', camera?.id] });
      toast.success('Zone perimeter synchronized');
      setDrawingMode('none');
    }
  });

  const updateZoneMutation = useMutation({
    mutationFn: ({ id, data }) => zonesAPI.updateZone(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['zones', camera?.id] });
      toast.success('Zone configuration updated');
    }
  });

  const deleteZoneMutation = useMutation({
    mutationFn: zonesAPI.deleteZone,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['zones', camera?.id] });
      toast.success('Zone decommissioned');
    }
  });

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw existing zones
    zones.forEach(zone => {
      const config = zone.config_json || {};
      ctx.beginPath();
      ctx.lineWidth = 3;
      ctx.strokeStyle = zone.is_active ? (zone.zone_type === 'exclusion' ? '#ef4444' : '#3b82f6') : '#525252';
      ctx.fillStyle = zone.is_active ? (zone.zone_type === 'exclusion' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(59, 130, 246, 0.15)') : 'rgba(82, 82, 82, 0.1)';

      if (config.shape === 'circle') {
        const { center, radius } = config;
        ctx.arc(center[0] * canvas.width, center[1] * canvas.height, radius * canvas.width, 0, Math.PI * 2);
      } else if (config.shape === 'square' || config.shape === 'rectangle') {
        const [x, y, w, h] = config.rect;
        ctx.rect(x * canvas.width, y * canvas.height, w * canvas.width, h * canvas.height);
      }

      ctx.fill();
      ctx.stroke();

      // Label
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 10px Inter';
      if (config.shape === 'circle' && config.center) {
        ctx.fillText(zone.name, config.center[0] * canvas.width, config.center[1] * canvas.height - 5);
      } else if (config.rect) {
        ctx.fillText(zone.name, config.rect[0] * canvas.width + 5, config.rect[1] * canvas.height + 15);
      }
    });

    // Draw active drawing
    if (isDrawing && startPos && currentPos) {
      ctx.beginPath();
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 5]);
      ctx.strokeStyle = '#3b82f6';
      
      if (drawingMode === 'circle') {
        const radius = Math.sqrt(Math.pow(currentPos.x - startPos.x, 2) + Math.pow(currentPos.y - startPos.y, 2));
        ctx.arc(startPos.x, startPos.y, radius, 0, Math.PI * 2);
      } else if (drawingMode === 'square') {
        ctx.rect(startPos.x, startPos.y, currentPos.x - startPos.x, currentPos.y - startPos.y);
      }
      
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }, [zones, isDrawing, startPos, currentPos, drawingMode]);

  useEffect(() => {
    draw();
  }, [draw]);

  const handleMouseDown = (e) => {
    if (drawingMode === 'none') return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setStartPos({ x, y });
    setCurrentPos({ x, y });
    setIsDrawing(true);
  };

  const handleMouseMove = (e) => {
    if (!isDrawing) return;
    const rect = canvasRef.current.getBoundingClientRect();
    setCurrentPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  const handleMouseUp = () => {
    if (!isDrawing) return;
    setIsDrawing(false);

    const canvas = canvasRef.current;
    const normX = startPos.x / canvas.width;
    const normY = startPos.y / canvas.height;
    const normW = (currentPos.x - startPos.x) / canvas.width;
    const normH = (currentPos.y - startPos.y) / canvas.height;

    const newZoneData = {
      camera_id: camera.id,
      name: `ZONE-${zones.length + 1}`,
      zone_type: 'exclusion',
      is_active: true,
      config_json: {
        shape: drawingMode,
        ...(drawingMode === 'circle' ? {
          center: [normX, normY],
          radius: Math.sqrt(Math.pow(normW, 2) + Math.pow(normH, 2))
        } : {
          rect: [normX, normY, normW, normH]
        })
      }
    };

    createZoneMutation.mutate(newZoneData);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/90 backdrop-blur-2xl animate-in fade-in duration-300" onClick={onClose} />
      
      <div className="relative bg-[#0d0d0f] border border-white/10 rounded-[40px] shadow-2xl w-full max-w-6xl overflow-hidden animate-in zoom-in-95 duration-300 flex h-[80vh]">
        
        {/* Left: Video & Drawing Area */}
        <div className="flex-1 relative bg-black flex items-center justify-center overflow-hidden">
          <div className="relative w-full h-full flex items-center justify-center bg-neutral-950">
            {isMediaLoading && (
              <div className="absolute inset-0 flex items-center justify-center bg-neutral-900/50 backdrop-blur-sm z-20">
                <div className="w-12 h-12 border-2 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
              </div>
            )}
            {isMjpeg ? (
              <img 
                src={streamUrl} 
                alt="Tactical Stream"
                className="w-full h-full object-contain opacity-50"
                onLoad={() => setIsMediaLoading(false)}
                onError={() => setIsMediaLoading(false)}
              />
            ) : (
              <video 
                src={streamUrl} 
                className="w-full h-full object-contain opacity-50"
                autoPlay muted loop playsInline
                onPlaying={() => setIsMediaLoading(false)}
                onCanPlay={() => setIsMediaLoading(false)}
                onError={() => setIsMediaLoading(false)}
              />
            )}
            <canvas
              ref={canvasRef}
              width={1280}
              height={720}
              className={`absolute inset-0 w-full h-full object-contain cursor-crosshair z-10`}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
            />
            
            {/* HUD Overlay */}
            <div className="absolute top-8 left-8 z-20 flex items-center space-x-4 pointer-events-none">
              <div className="p-3 bg-blue-600 rounded-2xl shadow-lg">
                <ShieldAlert className="w-6 h-6 text-white" />
              </div>
              <div>
                <h2 className="text-xl font-black text-white uppercase tracking-tighter">Perimeter Defense Architect</h2>
                <p className="text-neutral-500 text-[10px] font-black uppercase tracking-widest">{camera?.name} &bull; Coordinate Mapping</p>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Controls & List */}
        <div className="w-80 border-l border-white/10 flex flex-col bg-[#0d0d0f]">
          <header className="p-6 border-b border-white/5 flex justify-between items-center">
            <span className="text-[10px] font-black text-neutral-500 uppercase tracking-widest">Tactical Zones</span>
            <button onClick={onClose} className="p-2 hover:bg-white/5 rounded-full transition-colors">
              <X className="w-5 h-5 text-neutral-500" />
            </button>
          </header>

          <div className="p-6 space-y-6 flex-1 overflow-y-auto custom-scrollbar">
            {/* Tool Selection */}
            <div className="space-y-3">
              <p className="text-[9px] font-black text-neutral-600 uppercase tracking-widest">Drawing Tools</p>
              <div className="grid grid-cols-3 gap-2">
                <button 
                  onClick={() => setDrawingMode('none')}
                  className={`flex flex-col items-center justify-center p-3 rounded-2xl border transition-all ${drawingMode === 'none' ? 'bg-blue-600 border-blue-500 text-white shadow-lg' : 'bg-neutral-900 border-white/5 text-neutral-500 hover:text-white'}`}
                >
                  <MousePointer2 className="w-5 h-5 mb-1" />
                  <span className="text-[8px] font-bold uppercase">Select</span>
                </button>
                <button 
                  onClick={() => setDrawingMode('square')}
                  className={`flex flex-col items-center justify-center p-3 rounded-2xl border transition-all ${drawingMode === 'square' ? 'bg-blue-600 border-blue-500 text-white shadow-lg' : 'bg-neutral-900 border-white/5 text-neutral-500 hover:text-white'}`}
                >
                  <Square className="w-5 h-5 mb-1" />
                  <span className="text-[8px] font-bold uppercase">Square</span>
                </button>
                <button 
                  onClick={() => setDrawingMode('circle')}
                  className={`flex flex-col items-center justify-center p-3 rounded-2xl border transition-all ${drawingMode === 'circle' ? 'bg-blue-600 border-blue-500 text-white shadow-lg' : 'bg-neutral-900 border-white/5 text-neutral-500 hover:text-white'}`}
                >
                  <Circle className="w-5 h-5 mb-1" />
                  <span className="text-[8px] font-bold uppercase">Circle</span>
                </button>
              </div>
            </div>

            {/* Zones List */}
            <div className="space-y-3">
              <p className="text-[9px] font-black text-neutral-600 uppercase tracking-widest">Active Perimeters ({zones.length})</p>
              <div className="space-y-2">
                {zones.map(zone => (
                  <div key={zone.id} className={`group p-4 rounded-2xl border transition-all ${zone.is_active ? 'bg-neutral-900/50 border-white/5' : 'bg-neutral-900/20 border-white/5 opacity-60'}`}>
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center space-x-3">
                        <div className={`p-1.5 rounded-lg ${zone.is_active ? 'bg-blue-500/20 text-blue-400' : 'bg-neutral-800 text-neutral-600'}`}>
                          {zone.config_json?.shape === 'circle' ? <Circle className="w-3 h-3" /> : <Square className="w-3 h-3" />}
                        </div>
                        <span className="text-xs font-black text-white uppercase tracking-tight">{zone.name}</span>
                      </div>
                      <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button 
                          onClick={() => updateZoneMutation.mutate({ id: zone.id, data: { is_active: !zone.is_active } })}
                          className="p-1.5 hover:bg-white/5 rounded-lg transition-colors text-neutral-400 hover:text-white"
                        >
                          {zone.is_active ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
                        </button>
                        <button 
                          onClick={() => deleteZoneMutation.mutate(zone.id)}
                          className="p-1.5 hover:bg-red-500/10 rounded-lg transition-colors text-neutral-400 hover:text-red-400"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className={`text-[8px] font-black uppercase px-2 py-0.5 rounded-md ${zone.zone_type === 'exclusion' ? 'bg-red-500/10 text-red-400' : 'bg-blue-500/10 text-blue-400'}`}>
                        {zone.zone_type}
                      </span>
                      <select 
                        className="bg-transparent text-[8px] font-black uppercase text-neutral-500 outline-none cursor-pointer hover:text-white transition-colors"
                        value={zone.zone_type}
                        onChange={(e) => updateZoneMutation.mutate({ id: zone.id, data: { zone_type: e.target.value } })}
                      >
                        <option value="exclusion">Exclusion</option>
                        <option value="alert">Alert</option>
                        <option value="counting">Counting</option>
                      </select>
                    </div>
                  </div>
                ))}
                {zones.length === 0 && (
                  <div className="text-center py-8 border-2 border-dashed border-white/5 rounded-[32px]">
                    <Plus className="w-8 h-8 text-neutral-800 mx-auto mb-2" />
                    <p className="text-[10px] font-black text-neutral-700 uppercase">No perimeters defined</p>
                  </div>
                )}
              </div>
            </div>
          </div>

          <footer className="p-6 border-t border-white/5">
            <button 
              onClick={onClose}
              className="w-full flex items-center justify-center space-x-2 py-4 bg-blue-600 text-white text-[10px] font-black uppercase tracking-widest rounded-2xl shadow-xl shadow-blue-600/20 hover:bg-blue-500 transition-all active:scale-95"
            >
              <Target className="w-4 h-4" />
              <span>Finalize Sector Defense</span>
            </button>
          </footer>
        </div>
      </div>
    </div>
  );
};

export default ZoneManagerModal;
