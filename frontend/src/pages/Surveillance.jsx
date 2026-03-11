import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { 
  Grid,
  Filter
} from 'lucide-react';
import MultiCameraGrid from '../components/MultiCameraGrid';
import { camerasAPI } from '../utils/api';

const Surveillance = () => {
  const [gridLayout, setGridLayout] = useState('2x2'); // 1x1, 2x2, 3x3, 4x4
  const [selectedCameraId, setSelectedCameraId] = useState(null);
  const [filterModality, setFilterModality] = useState('all'); // all, rgb, thermal, mjpeg, fused
  
  // Fetch cameras
  const { data: cameras, isLoading } = useQuery({
    queryKey: ['cameras'],
    queryFn: camerasAPI.getCameras,
    refetchInterval: 30000,
  });

  const handleCameraSelect = (camera) => {
    setSelectedCameraId(camera.id);
  };

  const handleMaximize = (camera) => {
    setSelectedCameraId(camera.id);
    setGridLayout('1x1');
  };

  const filteredCameras = useMemo(() => {
    if (!Array.isArray(cameras)) return [];
    if (filterModality === 'all') return cameras;
    return cameras.filter(c => c.modality === filterModality || (c.modality === 'rgb' && filterModality === 'mjpeg' && (c.config_json?.mjpeg_url || c.mjpeg_url)));
  }, [cameras, filterModality]);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <div className="w-12 h-12 border-4 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
        <p className="text-neutral-500 font-bold uppercase tracking-widest text-xs">Initializing Nexus...</p>
      </div>
    );
  }

  return (
    <div className="h-screen bg-[#0a0a0c] text-neutral-200 flex flex-col overflow-hidden">
      <div className="p-4 lg:p-6 flex-1 flex flex-col min-h-0">
        <header className="flex justify-between items-center mb-6 shrink-0">
          <div>
            <div className="flex items-center space-x-3 mb-1">
              <div className="p-2 bg-blue-600/20 rounded-lg border border-blue-500/30">
                <Grid className="w-5 h-5 text-blue-400" />
              </div>
              <h1 className="text-2xl font-black bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent uppercase tracking-tighter">
                Surveillance Matrix
              </h1>
            </div>
            <p className="text-[10px] font-black uppercase tracking-widest text-neutral-500">
              {filteredCameras.filter(c => c.status === 'online').length} Nodes Active &bull; Real-Time Tactical Feed
            </p>
          </div>

          <div className="flex items-center space-x-4">
            {/* Modality Filter */}
            <div className="flex items-center space-x-2 bg-neutral-900/50 p-1 rounded-xl border border-white/5 backdrop-blur-xl shrink-0">
              <div className="px-3 flex items-center space-x-1 border-r border-white/5 text-neutral-500">
                <Filter className="w-3.5 h-3.5" />
              </div>
              {['all', 'rgb', 'thermal', 'mjpeg', 'fused'].map(modality => (
                <button
                  key={modality}
                  onClick={(e) => {
                    e.stopPropagation();
                    setFilterModality(modality);
                  }}
                  className={`px-3 py-1.5 rounded-lg text-[10px] font-black uppercase transition-all ${
                    filterModality === modality ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20' : 'text-neutral-500 hover:text-white'
                  }`}
                >
                  {modality}
                </button>
              ))}
            </div>

            {/* Layout Controls */}
            <div className="flex items-center space-x-2 bg-neutral-900/50 p-1 rounded-xl border border-white/5 backdrop-blur-xl shrink-0">
              {['1x1', '2x2', '3x3', '4x4'].map(layout => (
                <button
                  key={layout}
                  onClick={(e) => {
                    e.stopPropagation();
                    setGridLayout(layout);
                  }}
                  className={`px-3 py-1.5 rounded-lg text-[10px] font-black uppercase transition-all ${
                    gridLayout === layout ? 'bg-blue-600 text-white shadow-lg' : 'text-neutral-500 hover:text-white'
                  }`}
                >
                  {layout}
                </button>
              ))}
            </div>
          </div>
        </header>

        <div className="flex-1 bg-neutral-900/20 rounded-[40px] border border-white/5 overflow-hidden shadow-2xl relative">
          <MultiCameraGrid 
            cameras={filteredCameras}
            selectedCameraId={selectedCameraId}
            onCameraSelect={handleCameraSelect}
            onMaximize={handleMaximize}
            gridLayout={gridLayout}
          />
        </div>
      </div>
    </div>
  );
};

export default Surveillance;
