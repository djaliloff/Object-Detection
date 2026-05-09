import React, { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  X, 
  Save, 
  Camera, 
  Wifi, 
  Zap,
  Link as LinkIcon,
  RefreshCw
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
  const [sourceType, setSourceType] = useState(camera?.modality === 'video' ? 'video' : 'live');
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => {
    if (camera) {
      setFormData({
        ...camera,
        port: camera.port || 554,
        resolution: camera.resolution || '1920x1080',
        fps: camera.fps || 30
      });
      setSourceType(camera.modality === 'video' ? 'video' : 'live');
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
      setSourceType('live');
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

  const handleVideoUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setIsUploading(true);
    const loadingToast = toast.loading('Uploading tactical archive...');
    try {
      // Pass the current modality so the backend routes to RGB/ or Thermal/
      const response = await camerasAPI.uploadVideo(file, formData.modality);
      setFormData(prev => ({
        ...prev,
        rtsp_url: response.file_path,
        stream_url: response.web_url,
        ip: '0.0.0.0' // Placeholder for video files
      }));
      toast.success(
        `Archive staged in ${response.subfolder} folder`,
        { id: loadingToast }
      );
    } catch (err) {
      toast.error('Upload sequence failed', { id: loadingToast });
    } finally {
      setIsUploading(false);
    }
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

        <div className="px-8 pt-6">
          <div className="flex bg-neutral-900 rounded-2xl p-1 w-fit border border-white/5">
            <button 
              type="button"
              onClick={() => setSourceType('live')}
              className={`px-6 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${sourceType === 'live' ? 'bg-blue-600 text-white shadow-lg' : 'text-neutral-500 hover:text-white'}`}
            >
              Real-time Stream
            </button>
            <button 
              type="button"
              onClick={() => setSourceType('video')}
              className={`px-6 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${sourceType === 'video' ? 'bg-blue-600 text-white shadow-lg' : 'text-neutral-500 hover:text-white'}`}
            >
              Video Archive
            </button>
          </div>
        </div>

        <nav className="flex px-4 border-b border-white/5">
          <TabButton id="basic" label="Transmission" icon={Wifi} />
          <TabButton id="streams" label="Protocols" icon={LinkIcon} />
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
                  
                  {sourceType === 'live' ? (
                    <div className="group">
                      <label className="text-[10px] font-black uppercase tracking-widest text-neutral-600 block mb-2 group-focus-within:text-blue-500 transition-colors">Target IP</label>
                      <input
                        name="ip"
                        required
                        className="w-full bg-neutral-800/50 border border-white/5 rounded-2xl py-4 px-5 outline-none focus:ring-2 ring-blue-500/50 text-white font-bold transition-all placeholder:text-neutral-700"
                        placeholder="192.168.1.100"
                        value={formData.ip}
                        onChange={(e) => {
                          const val = e.target.value;
                          const ipMatch = val.match(/(\d{1,3}\.){3}\d{1,3}/);
                          if (ipMatch && val.includes('://')) {
                            setFormData(prev => ({
                              ...prev,
                              ip: ipMatch[0],
                              mjpeg_url: val.includes(':8080') ? val : prev.mjpeg_url,
                              rtsp_url: val.includes(':8080') ? `rtsp://${ipMatch[0]}:8080/h264_pcm.sdp` : prev.rtsp_url
                            }));
                            toast.success(`Smart extracted IP: ${ipMatch[0]}`, { icon: '🤖' });
                          } else {
                            handleChange(e);
                          }
                        }}
                      />
                    </div>
                  ) : (
                    <div className="group">
                      <label className="text-[10px] font-black uppercase tracking-widest text-neutral-600 block mb-2 group-focus-within:text-blue-500 transition-colors">Tactical Archive (Video)</label>
                      <div className="relative">
                        <input
                          type="file"
                          accept="video/*"
                          onChange={handleVideoUpload}
                          disabled={isUploading}
                          className="hidden"
                          id="video-upload"
                        />
                        <label 
                          htmlFor="video-upload"
                          className="w-full flex items-center justify-center space-x-3 bg-blue-600/10 border border-blue-500/20 border-dashed rounded-2xl py-8 cursor-pointer hover:bg-blue-600/20 transition-all group/upload"
                        >
                          <div className={`p-3 bg-blue-600 rounded-xl shadow-lg ${isUploading ? 'animate-pulse' : 'group-hover/upload:scale-110'} transition-transform`}>
                            {isUploading ? <RefreshCw className="w-5 h-5 text-white animate-spin" /> : <Save className="w-5 h-5 text-white" />}
                          </div>
                          <div className="text-left">
                            <p className="text-[10px] font-black text-white uppercase tracking-widest">{isUploading ? 'Uploading Archive...' : 'Select Video File'}</p>
                            <p className="text-[8px] font-bold text-blue-400/60 uppercase">{formData.rtsp_url ? 'File Staged' : 'MP4, MKV, AVI supported'}</p>
                          </div>
                        </label>
                      </div>
                      {formData.rtsp_url && (
                        <p className="mt-2 text-[8px] font-mono text-neutral-500 truncate">{formData.rtsp_url}</p>
                      )}
                    </div>
                  )}
                </div>
                <div className="space-y-6">
                  <div className="group">
                    <label className="text-[10px] font-black uppercase tracking-widest text-neutral-600 block mb-2 group-focus-within:text-blue-500 transition-colors">Optic Class</label>
                    <div className="flex bg-neutral-900 rounded-2xl p-1 border border-white/5">
                      <button
                        type="button"
                        onClick={() => setFormData(prev => ({ ...prev, modality: 'rgb' }))}
                        className={`flex-1 px-4 py-3 rounded-xl text-xs font-bold uppercase tracking-wider transition-all ${
                          formData.modality === 'rgb'
                            ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20' 
                            : 'text-neutral-500 hover:text-white'
                        }`}
                      >
                        RGB Standard
                      </button>
                      <button
                        type="button"
                        onClick={() => setFormData(prev => ({ ...prev, modality: 'thermal' }))}
                        className={`flex-1 px-4 py-3 rounded-xl text-xs font-bold uppercase tracking-wider transition-all ${
                          formData.modality === 'thermal'
                            ? 'bg-orange-600 text-white shadow-lg shadow-orange-500/20' 
                            : 'text-neutral-500 hover:text-white'
                        }`}
                      >
                        Thermique
                      </button>
                    </div>
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
                  
                  {/* AI Detection Toggle */}
                  <div className="flex items-center justify-between p-4 bg-blue-600/5 rounded-2xl border border-blue-500/10">
                    <div className="flex items-center space-x-3">
                      <div className={`p-2 rounded-lg ${formData.detection_enabled ? 'bg-blue-600 text-white' : 'bg-neutral-800 text-neutral-500'}`}>
                        <Zap className="w-4 h-4" />
                      </div>
                      <div>
                        <p className="text-[10px] font-black text-white uppercase tracking-widest">AI Detection (YOLO)</p>
                        <p className="text-[8px] font-bold text-neutral-500 uppercase">Real-time object analysis</p>
                      </div>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input 
                        type="checkbox" 
                        name="detection_enabled"
                        className="sr-only peer" 
                        checked={formData.detection_enabled}
                        onChange={handleChange}
                      />
                      <div className="w-11 h-6 bg-neutral-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                    </label>
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
