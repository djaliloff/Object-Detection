import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { 
  Camera, 
  AlertTriangle, 
  Activity,
  Eye,
  Users,
  Clock,
  Grid3x3,
  Settings,
  RefreshCw,
  Bell,
  BellOff,
  Download,
  Share2,
  Monitor,
  Zap,
  Shield,
  Layout as LayoutIcon,
  Circle
} from 'lucide-react';
import toast from 'react-hot-toast';

import MultiCameraGrid from '../components/MultiCameraGrid';
import StatCard from '../components/StatCard';
import EventTimeline from '../components/EventTimeline';
import CameraControls from '../components/CameraControls';
import VideoPlayer from '../components/VideoPlayer';
import { analyticsAPI, eventsAPI, camerasAPI } from '../utils/api';

const Dashboard = () => {
  const [selectedCamera, setSelectedCamera] = useState(null);
  const [viewMode, setViewMode] = useState('single'); // single, grid, timeline
  const [isRecording, setIsRecording] = useState(false);
  const [alertsEnabled, setAlertsEnabled] = useState(true);

  // Fetch analytics summary
  const { data: analytics, isLoading: analyticsLoading } = useQuery({
    queryKey: ['analytics-summary'],
    queryFn: analyticsAPI.getSummary,
    refetchInterval: 30000,
  });

  // Fetch recent events
  const { data: events, isLoading: eventsLoading } = useQuery({
    queryKey: ['recent-events'],
    queryFn: () => eventsAPI.getEvents({ limit: 12, status: 'new' }),
    refetchInterval: 10000,
  });

  // Fetch cameras
  const { data: cameras } = useQuery({
    queryKey: ['cameras'],
    queryFn: camerasAPI.getCameras,
    refetchInterval: 60000,
  });

  useEffect(() => {
    if (cameras && cameras.length > 0 && !selectedCamera) {
      setSelectedCamera(cameras[0]);
    }
  }, [cameras, selectedCamera]);

  const handleCameraSelect = (camera) => {
    setSelectedCamera(camera);
    setViewMode('single');
    toast.success(`Switching to: ${camera.name}`, {
      style: {
        background: 'rgba(30, 41, 59, 0.9)',
        color: '#fff',
        backdropFilter: 'blur(10px)',
        border: '1px solid rgba(255,255,255,0.1)'
      }
    });
  };

  const handleToggleRecording = () => {
    setIsRecording(!isRecording);
    if (!isRecording) {
      toast.error('Recording started', { icon: '🔴' });
    } else {
      toast.success('Recording saved to archive');
    }
  };

  const handlePTZControl = (direction) => {
    console.log(`PTZ ${direction} for camera ${selectedCamera?.id}`);
    toast(`Adjusting PTZ: ${direction}`, { icon: '🕹️' });
  };

  const handleZoomControl = (zoomLevel) => {
    console.log(`Zoom to ${zoomLevel}% for camera ${selectedCamera?.id}`);
  };

  const handleTakeSnapshot = () => {
    toast.success('Snapshot captured', { icon: '📸' });
  };

  const handleOpenSettings = () => {
    toast.success('Loading camera configuration...');
  };

  const getEventIcon = (eventType) => {
    switch (eventType) {
      case 'intrusion': return <Shield className="w-4 h-4 text-red-500" />;
      case 'loitering': return <Clock className="w-4 h-4 text-yellow-500" />;
      case 'line_crossing': return <Activity className="w-4 h-4 text-blue-500" />;
      case 'abandoned_object': return <AlertTriangle className="w-4 h-4 text-orange-500" />;
      default: return <Activity className="w-4 h-4 text-gray-500" />;
    }
  };

  const getSeverityGlow = (severity) => {
    switch (severity) {
      case 'critical': return 'shadow-[0_0_15px_rgba(239,68,68,0.3)] border-red-500/50';
      case 'high': return 'shadow-[0_0_10px_rgba(249,115,22,0.2)] border-orange-500/40';
      case 'medium': return 'shadow-[0_0_10px_rgba(234,179,8,0.1)] border-yellow-500/30';
      default: return 'border-white/5';
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0c] text-neutral-200 selection:bg-blue-500/30">
      {/* Dynamic Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-600/5 blur-[120px] rounded-full" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-600/5 blur-[120px] rounded-full" />
      </div>

      <div className="relative z-10 p-4 lg:p-8">
        {/* Header Section */}
        <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-8">
          <div>
            <div className="flex items-center space-x-3 mb-1">
              <div className="p-2 bg-blue-600/20 rounded-lg border border-blue-500/30">
                <LayoutIcon className="w-6 h-6 text-blue-400" />
              </div>
              <h1 className="text-3xl font-black bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent">
                Command Center
              </h1>
            </div>
            <p className="text-neutral-500 font-medium">System operational &bull; {Array.isArray(cameras) ? cameras.filter(c => c.status === 'online').length : 0} active nodes</p>
          </div>

          <div className="flex items-center space-x-2 bg-neutral-900/50 p-1.5 rounded-2xl border border-white/5 backdrop-blur-xl">
            <button
              onClick={() => setViewMode('single')}
              className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-sm font-bold transition-all ${
                viewMode === 'single' ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/25' : 'text-neutral-500 hover:text-white'
              }`}
            >
              <Monitor className="w-4 h-4" />
              <span>Direct</span>
            </button>
            <button
              onClick={() => setViewMode('grid')}
              className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-sm font-bold transition-all ${
                viewMode === 'grid' ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/25' : 'text-neutral-500 hover:text-white'
              }`}
            >
              <Grid3x3 className="w-4 h-4" />
              <span>Grid</span>
            </button>
            <div className="w-px h-6 bg-white/5 mx-1" />
            <button
              onClick={() => setAlertsEnabled(!alertsEnabled)}
              className={`p-2 rounded-xl transition-all ${alertsEnabled ? 'text-blue-400 bg-blue-500/10' : 'text-neutral-500'}`}
            >
              {alertsEnabled ? <Bell className="w-5 h-5" /> : <BellOff className="w-5 h-5" />}
            </button>
          </div>
        </header>

        {/* Tactical Overview Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard
            title="Active Eyes"
            value={analytics?.online_cameras || 0}
            total={analytics?.total_cameras || 0}
            icon={<Camera className="w-5 h-5" />}
            trend="+2 today"
            color="blue"
            loading={analyticsLoading}
          />
          <StatCard
            title="Critical Threats"
            value={analytics?.new_events || 0}
            icon={<Shield className="w-5 h-5" />}
            trend="Active now"
            color="red"
            loading={analyticsLoading}
          />
          <StatCard
            title="Detections"
            value={analytics?.total_detections || 0}
            icon={<Eye className="w-5 h-5" />}
            trend="Rolling 24h"
            color="purple"
            loading={analyticsLoading}
          />
          <StatCard
            title="Neural Load"
            value="34%"
            icon={<Zap className="w-5 h-5" />}
            trend="Stable"
            color="green"
            loading={analyticsLoading}
          />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
          {/* Visual Matrix */}
          <main className="xl:col-span-9 space-y-6">
            <div className="bg-neutral-900/40 border border-white/5 rounded-3xl overflow-hidden backdrop-blur-2xl shadow-inner">
              {viewMode === 'single' ? (
                <div className="flex flex-col">
                  <div className="p-6 border-b border-white/5 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                    <div className="flex items-center space-x-4">
                      <div className="relative">
                        <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg">
                          <Camera className="w-6 h-6 text-white" />
                        </div>
                        <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-green-500 border-2 border-[#0a0a0c] rounded-full" />
                      </div>
                      <div>
                        <h2 className="text-xl font-bold text-white leading-tight">{selectedCamera?.name || 'Loading Matrix...'}</h2>
                        <div className="flex items-center space-x-2 text-xs text-neutral-500 mt-1 font-bold tracking-wider uppercase">
                          <span>{selectedCamera?.resolution || '4K'}</span>
                          <span>&bull;</span>
                          <span>{selectedCamera?.fps || '60'} FPS</span>
                          <span>&bull;</span>
                          <span className="text-blue-400">{selectedCamera?.ip}</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center space-x-2">
                       <select 
                        value={selectedCamera?.id || ''} 
                        onChange={(e) => {
                          const id = e.target.value;
                          const cam = Array.isArray(cameras) ? cameras.find(c => c.id === id) : null;
                          if (cam) handleCameraSelect(cam);
                        }}
                        className="bg-neutral-800/80 text-white text-xs font-bold px-4 py-2.5 rounded-xl border border-white/10 focus:ring-2 ring-blue-500/50 outline-none transition-all cursor-pointer"
                      >
                        {Array.isArray(cameras) && cameras.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                      </select>
                      <button className="p-2.5 rounded-xl bg-neutral-800/80 border border-white/10 hover:bg-neutral-700 transition-colors">
                        <Settings className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  <div className="p-4">
                    <div className="aspect-video relative rounded-2xl overflow-hidden bg-black shadow-2xl">
                      {selectedCamera ? (
                        <VideoPlayer camera={selectedCamera} />
                      ) : (
                        <div className="absolute inset-0 flex items-center justify-center">
                          <RefreshCw className="w-8 h-8 text-neutral-800 animate-spin" />
                        </div>
                      )}
                    </div>
                  </div>

                  {selectedCamera && (
                    <div className="px-4 pb-4">
                      <div className="p-4 bg-white/5 rounded-2xl border border-white/5">
                         <CameraControls 
                          camera={selectedCamera}
                          isRecording={isRecording}
                          onToggleRecording={handleToggleRecording}
                          onTakeSnapshot={handleTakeSnapshot}
                          onPTZControl={handlePTZControl}
                          onZoomControl={handleZoomControl}
                          onOpenSettings={handleOpenSettings}
                        />
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-6">
                  <MultiCameraGrid 
                    cameras={cameras || []}
                    onCameraSelect={handleCameraSelect}
                    selectedCameraId={selectedCamera?.id}
                  />
                </div>
              )}
            </div>

            {/* Event Analysis */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="md:col-span-2 bg-neutral-900/40 border border-white/5 rounded-3xl p-6 backdrop-blur-2xl">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-lg font-bold flex items-center space-x-2">
                    <Activity className="w-5 h-5 text-blue-400" />
                    <span>Live Intelligence</span>
                  </h3>
                  <button className="text-xs font-bold uppercase tracking-widest text-neutral-500 hover:text-white transition-colors">
                    View All
                  </button>
                </div>
                <div className="h-64 overflow-hidden relative">
                   <EventTimeline />
                </div>
              </div>

              <div className="bg-gradient-to-br from-blue-600 to-indigo-700 rounded-3xl p-6 shadow-xl shadow-blue-900/20 relative overflow-hidden group">
                <div className="absolute top-[-20%] right-[-20%] w-64 h-64 bg-white/10 rounded-full blur-3xl group-hover:scale-125 transition-transform duration-700" />
                <div className="relative z-10 flex flex-col h-full">
                  <Shield className="w-10 h-10 text-white/40 mb-4" />
                  <h3 className="text-xl font-black text-white leading-tight mb-2">Secure Export</h3>
                  <p className="text-white/70 text-sm mb-auto">Generate certified evidence packages with encrypted timestamps and metadata.</p>
                  <button className="mt-8 flex items-center justify-center space-x-2 bg-white text-blue-600 py-3 rounded-2xl font-bold hover:bg-neutral-100 transition-all shadow-lg active:scale-95">
                    <Download className="w-5 h-5" />
                    <span>Archive Data</span>
                  </button>
                </div>
              </div>
            </div>
          </main>

          {/* Neural Feed Sidebar */}
          <aside className="xl:col-span-3 space-y-6">
            <div className="bg-neutral-900/40 border border-white/5 rounded-3xl p-6 backdrop-blur-2xl flex flex-col h-full max-h-[1000px]">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-bold flex items-center space-x-2">
                  <Zap className="w-5 h-5 text-yellow-400" />
                  <span>Neural Feed</span>
                </h3>
                <div className="flex items-center space-x-1.5 px-2.5 py-1 bg-green-500/10 text-green-400 rounded-full text-[10px] font-black uppercase tracking-widest border border-green-500/20">
                  <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
                  <span>Real-time</span>
                </div>
              </div>

              <div className="space-y-4 overflow-y-auto pr-2 custom-scrollbar">
                {eventsLoading ? (
                  <div className="flex flex-col items-center justify-center py-20 space-y-4">
                    <div className="w-10 h-10 border-4 border-white/5 border-t-blue-500 rounded-full animate-spin" />
                    <p className="text-xs font-bold text-neutral-600 uppercase tracking-widest">Scanning Network</p>
                  </div>
                ) : events?.data?.map((event) => (
                  <div
                    key={event.id}
                    className={`group relative bg-white/5 border rounded-2xl p-4 hover:bg-white/[0.08] transition-all cursor-pointer ${getSeverityGlow(event.severity)}`}
                    onClick={() => handleCameraSelect(cameras?.find(c => c.id === event.camera_id))}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center space-x-3">
                        <div className="p-2 bg-neutral-800 rounded-xl group-hover:scale-110 transition-transform">
                          {getEventIcon(event.event_type)}
                        </div>
                        <div>
                          <p className="text-xs font-black uppercase tracking-wider text-white truncate w-32">
                            {event.event_type.replace('_', ' ')}
                          </p>
                          <p className="text-[10px] font-bold text-neutral-500">
                            {new Date(event.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </p>
                        </div>
                      </div>
                      <div className={`px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-widest ${
                        event.severity === 'critical' ? 'bg-red-500/20 text-red-500' : 'bg-neutral-800 text-neutral-400'
                      }`}>
                        {event.severity}
                      </div>
                    </div>
                    
                    {event.event_data?.object_class && (
                      <div className="flex items-center space-x-2 mt-2 px-2 py-1.5 bg-black/30 rounded-lg border border-white/5">
                        <Users className="w-3 h-3 text-blue-400" />
                        <span className="text-[10px] font-bold text-neutral-300">Target: {event.event_data.object_class}</span>
                        <div className="ml-auto flex items-center space-x-1">
                          <Circle className="w-1.5 h-1.5 text-blue-500 fill-blue-500" />
                          <span className="text-[10px] font-black text-blue-500">{Math.round(event.event_data.confidence * 100)}%</span>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
            
            <div className="p-1 group">
              <button className="w-full bg-neutral-900 border border-white/5 hover:border-blue-500/30 p-4 rounded-2xl flex items-center justify-between transition-all hover:translate-y-[-2px]">
                <div className="flex items-center space-x-3">
                  <div className="w-8 h-8 rounded-lg bg-neutral-800 flex items-center justify-center">
                    <Share2 className="w-4 h-4 text-neutral-400 group-hover:text-blue-400" />
                  </div>
                  <span className="text-sm font-bold">Network Status</span>
                </div>
                <div className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full" />
                  <span className="text-xs font-bold text-green-500 font-mono">99.9%</span>
                </div>
              </button>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
