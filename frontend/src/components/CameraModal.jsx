import React, { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  X, 
  Save, 
  Camera, 
  Shield, 
  Activity, 
  Wifi, 
  Monitor,
  Zap,
  Bot,
  Settings,
  Link as LinkIcon
} from 'lucide-react';
import toast from 'react-hot-toast';
import { camerasAPI } from '../utils/api';

const CameraModal = ({ isOpen, onClose, camera = null }) => {
  const queryClient = useQueryClient();
  const isEditing = !!camera;

  const [formData, setFormData] = useState({
    name: '',
    ip: '',
    port: 554,
    rtsp_url: '',
    hls_url: '',
    webrtc_url: '',
    mjpeg_url: '',
    stream_url: '',
    modality: 'rgb',
    status: 'online',
    location: '',
    resolution: '1920x1080',
    fps: 30,
    is_active: true,
    is_recording: false,
    detection_enabled: true,
    ptz_enabled: false,
    thermal_min: 20,
    thermal_max: 45
  });

  const [activeTab, setActiveTab] = useState('basic');

  useEffect(() => {
    if (camera) {
      setFormData({
        ...camera,
        port: camera.port || 554,
        resolution: camera.resolution || '1920x1080',
        fps: camera.fps || 30
      });
    } else {
      setFormData({
        name: '',
        ip: '',
        port: 554,
        rtsp_url: '',
        hls_url: '',
        webrtc_url: '',
        mjpeg_url: '',
        stream_url: '',
        modality: 'rgb',
        status: 'online',
        location: '',
        resolution: '1920x1080',
        fps: 30,
        is_active: true,
        is_recording: false,
        detection_enabled: true,
        ptz_enabled: false,
        thermal_min: 20,
        thermal_max: 45
      });
    }
  }, [camera, isOpen]);

  const mutation = useMutation({
    mutationFn: (data) => {
      if (isEditing) {
        return camerasAPI.updateCamera(camera.id, data);
      }
      return camerasAPI.createCamera(data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cameras'] });
      toast.success(isEditing ? 'Node reconfigured' : 'New node deployed');
      onClose();
    },
    onError: (err) => {
      toast.error('System synchronization failed');
      console.error(err);
    },
  });

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : (type === 'number' ? Number(value) : value)
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    mutation.mutate(formData);
  };

  if (!isOpen) return null;

  const TabButton = ({ id, label, icon: Icon }) => (
    <button
      onClick={() => setActiveTab(id)}
      className={`flex items-center space-x-2 px-6 py-3 border-b-2 transition-all font-bold text-sm ${
        activeTab === id 
          ? 'border-blue-500 text-blue-400 bg-blue-500/5' 
          : 'border-transparent text-neutral-500 hover:text-white'
      }`}
    >
      <Icon className="w-4 h-4" />
      <span>{label}</span>
    </button>
  );

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/80 backdrop-blur-xl animate-in fade-in duration-300" onClick={onClose} />
      
      <div className="relative bg-[#0d0d0f] border border-white/10 rounded-[40px] shadow-2xl w-full max-w-4xl overflow-hidden animate-in zoom-in-95 duration-300">
        <header className="p-8 border-b border-white/5 flex justify-between items-center bg-gradient-to-r from-blue-600/5 to-transparent">
          <div className="flex items-center space-x-4">
            <div className="p-3 bg-blue-600 rounded-2xl shadow-lg shadow-blue-600/20">
              <Camera className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-2xl font-black text-white uppercase tracking-tight">
                {isEditing ? 'Reconfigure Deployment' : 'Deploy New Node'}
              </h2>
              <p className="text-neutral-500 text-sm font-medium">Tactical Surveillance Interface v3.0</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 text-neutral-500 hover:text-white transition-colors bg-white/5 rounded-full hover:bg-white/10">
            <X className="w-6 h-6" />
          </button>
        </header>

        <nav className="flex px-4 border-b border-white/5">
          <TabButton id="basic" label="Transmission" icon={Wifi} />
          <TabButton id="streams" label="Protocols" icon={LinkIcon} />
          <TabButton id="analytics" label="Neural Ops" icon={Bot} />
          <TabButton id="advanced" label="System" icon={Settings} />
        </nav>

        <form onSubmit={handleSubmit} className="p-8">
          <div className="h-[450px] overflow-y-auto pr-4 custom-scrollbar">
            {activeTab === 'basic' && (
              <div className="grid grid-cols-2 gap-8 animate-in fade-in slide-in-from-bottom-4 duration-300">
                <div className="space-y-6">
                  <div className="group">
                    <label className="text-[10px] font-black uppercase tracking-widest text-neutral-600 block mb-2 group-focus-within:text-blue-500 transition-colors">Identifier</label>
                    <input
                      name="name"
                      required
                      className="w-full bg-neutral-800/50 border border-white/5 rounded-2xl py-4 px-5 outline-none focus:ring-2 ring-blue-500/50 text-white font-bold transition-all placeholder:text-neutral-700"
                      placeholder="e.g. ALPHA-1-MAIN"
                      value={formData.name}
                      onChange={handleChange}
                    />
                  </div>
                  <div className="group">
                    <label className="text-[10px] font-black uppercase tracking-widest text-neutral-600 block mb-2 group-focus-within:text-blue-500 transition-colors">Target IP</label>
                    <input
                      name="ip"
                      required
                      className="w-full bg-neutral-800/50 border border-white/5 rounded-2xl py-4 px-5 outline-none focus:ring-2 ring-blue-500/50 text-white font-bold transition-all placeholder:text-neutral-700"
                      placeholder="192.168.1.100"
                      value={formData.ip}
                      onChange={handleChange}
                    />
                  </div>
                </div>
                <div className="space-y-6">
                  <div className="group">
                    <label className="text-[10px] font-black uppercase tracking-widest text-neutral-600 block mb-2 group-focus-within:text-blue-500 transition-colors">Optic Class</label>
                    <select
                      name="modality"
                      className="w-full bg-neutral-800/50 border border-white/5 rounded-2xl py-4 px-5 outline-none focus:ring-2 ring-blue-500/50 text-white font-bold transition-all appearance-none cursor-pointer"
                      value={formData.modality}
                      onChange={handleChange}
                    >
                      <option value="rgb">RGB (Standard Visual)</option>
                      <option value="thermal">Thermal (Heat Signature)</option>
                      <option value="fused">Fused (Multispectral)</option>
                      <option value="mjpeg">MJPEG (Network Stream)</option>
                    </select>
                  </div>
                  <div className="group">
                    <label className="text-[10px] font-black uppercase tracking-widest text-neutral-600 block mb-2 group-focus-within:text-blue-500 transition-colors">Strategic Zone</label>
                    <input
                      name="location"
                      className="w-full bg-neutral-800/50 border border-white/5 rounded-2xl py-4 px-5 outline-none focus:ring-2 ring-blue-500/50 text-white font-bold transition-all placeholder:text-neutral-700"
                      placeholder="e.g. Sector 7-G"
                      value={formData.location}
                      onChange={handleChange}
                    />
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'streams' && (
              <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-300">
                <div className="p-6 bg-blue-500/5 rounded-[32px] border border-blue-500/10 mb-8">
                   <p className="text-xs text-blue-400 font-bold flex items-center mb-0">
                    <Zap className="w-4 h-4 mr-2" />
                    Protocol priority is automatically determined. IP Webcam usually utilizes MJPEG on :8080/video
                   </p>
                </div>
                <div className="grid grid-cols-1 gap-6">
                  <div className="group">
                    <label className="text-[10px] font-black uppercase tracking-widest text-neutral-600 block mb-2 group-focus-within:text-blue-500 transition-colors">HLS (Low Latency Web)</label>
                    <input
                      name="hls_url"
                      className="w-full bg-neutral-800/50 border border-white/5 rounded-2xl py-4 px-5 outline-none focus:ring-2 ring-blue-500/50 text-white font-mono text-xs transition-all placeholder:text-neutral-700"
                      placeholder="http://server/live/camera/index.m3u8"
                      value={formData.hls_url}
                      onChange={handleChange}
                    />
                  </div>
                  <div className="group">
                    <label className="text-[10px] font-black uppercase tracking-widest text-neutral-600 block mb-2 group-focus-within:text-blue-500 transition-colors">MJPEG / Direct Feed (IP Webcam)</label>
                    <input
                      name="mjpeg_url"
                      className="w-full bg-neutral-800/50 border border-white/5 rounded-2xl py-4 px-5 outline-none focus:ring-2 ring-blue-500/50 text-white font-mono text-xs transition-all placeholder:text-neutral-700"
                      placeholder="http://10.123.122.34:8080/video"
                      value={formData.mjpeg_url}
                      onChange={handleChange}
                    />
                  </div>
                   <div className="group">
                    <label className="text-[10px] font-black uppercase tracking-widest text-neutral-600 block mb-2 group-focus-within:text-blue-500 transition-colors">RTSP (Raw Stream)</label>
                    <input
                      name="rtsp_url"
                      className="w-full bg-neutral-800/50 border border-white/5 rounded-2xl py-4 px-5 outline-none focus:ring-2 ring-blue-500/50 text-white font-mono text-xs transition-all placeholder:text-neutral-700"
                      placeholder="rtsp://admin:pass@192.168.1.100:554/live"
                      value={formData.rtsp_url}
                      onChange={handleChange}
                    />
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'analytics' && (
              <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-300">
                <div className="grid grid-cols-2 gap-6">
                  <label className="flex items-center justify-between p-6 bg-white/5 border border-white/10 rounded-[32px] cursor-pointer hover:bg-white/[0.08] transition-all group">
                    <div className="flex items-center space-x-4">
                      <div className="p-3 bg-indigo-500/20 text-indigo-400 rounded-2xl group-hover:scale-110 transition-transform">
                        <Bot className="w-6 h-6" />
                      </div>
                      <div>
                        <p className="text-white font-bold uppercase tracking-tight">Object Detection</p>
                        <p className="text-neutral-600 text-[10px] font-black uppercase">TensorCore Analysis</p>
                      </div>
                    </div>
                    <input 
                      type="checkbox" 
                      name="detection_enabled" 
                      checked={formData.detection_enabled} 
                      onChange={handleChange}
                      className="w-6 h-6 accent-blue-600 bg-neutral-800 border-white/5 rounded-lg" 
                    />
                  </label>

                  <label className="flex items-center justify-between p-6 bg-white/5 border border-white/10 rounded-[32px] cursor-pointer hover:bg-white/[0.08] transition-all group">
                    <div className="flex items-center space-x-4">
                      <div className="p-3 bg-red-500/20 text-red-400 rounded-2xl group-hover:scale-110 transition-transform">
                        <Shield className="w-6 h-6" />
                      </div>
                      <div>
                        <p className="text-white font-bold uppercase tracking-tight">Active Sentinel</p>
                        <p className="text-neutral-600 text-[10px] font-black uppercase">Real-time alerts</p>
                      </div>
                    </div>
                    <input 
                      type="checkbox" 
                      name="is_active" 
                      checked={formData.is_active} 
                      onChange={handleChange}
                      className="w-6 h-6 accent-blue-600 bg-neutral-800 border-white/5 rounded-lg" 
                    />
                  </label>
                </div>

                <div className="p-8 bg-neutral-900 border border-white/5 rounded-[40px]">
                   <label className="text-[10px] font-black uppercase tracking-widest text-neutral-600 block mb-6">Object Confidence Threshold</label>
                   <div className="flex items-center space-x-6">
                      <input type="range" className="flex-1 accent-blue-600 h-1.5" />
                      <span className="text-2xl font-black text-blue-500 font-mono">85%</span>
                   </div>
                </div>
              </div>
            )}

            {activeTab === 'advanced' && (
              <div className="grid grid-cols-2 gap-8 animate-in fade-in slide-in-from-bottom-4 duration-300">
                <div className="space-y-6">
                  <div className="group">
                    <label className="text-[10px] font-black uppercase tracking-widest text-neutral-600 block mb-2 group-focus-within:text-blue-500 transition-colors">Target Resolution</label>
                    <select
                      name="resolution"
                      className="w-full bg-neutral-800/50 border border-white/5 rounded-2xl py-4 px-5 outline-none focus:ring-2 ring-blue-500/50 text-white font-bold transition-all appearance-none"
                      value={formData.resolution}
                      onChange={handleChange}
                    >
                      <option value="3840x2160">4K UHD (2160p)</option>
                      <option value="1920x1080">Full HD (1080p)</option>
                      <option value="1280x720">HD (720p)</option>
                      <option value="640x480">VGA (Thermal)</option>
                    </select>
                  </div>
                   <div className="group">
                    <label className="text-[10px] font-black uppercase tracking-widest text-neutral-600 block mb-2 group-focus-within:text-blue-500 transition-colors">Frame Frequency</label>
                    <input
                      type="number"
                      name="fps"
                      className="w-full bg-neutral-800/50 border border-white/5 rounded-2xl py-4 px-5 outline-none focus:ring-2 ring-blue-500/50 text-white font-bold transition-all"
                      value={formData.fps}
                      onChange={handleChange}
                    />
                  </div>
                </div>
                <div className="space-y-6">
                  <label className="flex items-center justify-between p-6 bg-white/5 border border-white/10 rounded-[32px] cursor-pointer hover:bg-white/[0.08] transition-all group">
                    <div className="flex items-center space-x-4">
                      <div className="p-3 bg-purple-500/20 text-purple-400 rounded-2xl group-hover:scale-110 transition-transform">
                        <Monitor className="w-6 h-6" />
                      </div>
                      <div>
                        <p className="text-white font-bold uppercase tracking-tight">PTZ Control</p>
                        <p className="text-neutral-600 text-[10px] font-black uppercase">Telemetery enabled</p>
                      </div>
                    </div>
                    <input 
                      type="checkbox" 
                      name="ptz_enabled" 
                      checked={formData.ptz_enabled} 
                      onChange={handleChange}
                      className="w-6 h-6 accent-blue-600 bg-neutral-800 border-white/5 rounded-lg" 
                    />
                  </label>
                  <label className="flex items-center justify-between p-6 bg-white/5 border border-white/10 rounded-[32px] cursor-pointer hover:bg-white/[0.08] transition-all group">
                    <div className="flex items-center space-x-4">
                      <div className="p-3 bg-red-500/20 text-red-400 rounded-2xl group-hover:scale-110 transition-transform">
                        <Activity className="w-6 h-6" />
                      </div>
                      <div>
                        <p className="text-white font-bold uppercase tracking-tight">24/7 Archives</p>
                        <p className="text-neutral-600 text-[10px] font-black uppercase">Persistent storage</p>
                      </div>
                    </div>
                    <input 
                      type="checkbox" 
                      name="is_recording" 
                      checked={formData.is_recording} 
                      onChange={handleChange}
                      className="w-6 h-6 accent-blue-600 bg-neutral-800 border-white/5 rounded-lg" 
                    />
                  </label>
                </div>
              </div>
            )}
          </div>

          <footer className="mt-8 flex justify-end space-x-4">
            <button
              type="button"
              onClick={onClose}
              className="px-8 py-4 bg-neutral-900 text-neutral-400 font-black uppercase tracking-widest text-xs rounded-2xl border border-white/5 hover:bg-neutral-800 transition-all active:scale-95"
            >
              Abort Mission
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="flex items-center space-x-2 px-10 py-4 bg-blue-600 text-white font-black uppercase tracking-widest text-xs rounded-2xl shadow-xl shadow-blue-600/30 hover:bg-blue-500 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {mutation.isPending ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              <span>Initialize Node</span>
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
};

export default CameraModal;
