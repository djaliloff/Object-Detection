import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { 
  Settings as SettingsIcon, 
  User, 
  Database, 
  Shield, 
  Cpu, 
  Globe, 
  Bell, 
  Save,
  Trash2,
  RefreshCw,
  Plus,
  Lock,
  ChevronRight,
  Activity,
  Server,
  Network
} from 'lucide-react';
import toast from 'react-hot-toast';
import { usersAPI } from '../utils/api';

const Settings = () => {
  const [activeCategory, setActiveCategory] = useState('general');

  // Form states
  const [retentionDays, setRetentionDays] = useState(30);
  const [autoPrune, setAutoPrune] = useState(true);
  const [activeModels, setActiveModels] = useState({ yolo: true, thermal: true, face: false });
  const [webhooks, setWebhooks] = useState('https://hooks.slack.com/services/...');
  const [notifications, setNotifications] = useState({ email: true, push: true, sms: false });

  const categories = [
    { id: 'general', label: 'Tactical Config', icon: SettingsIcon },
    { id: 'users', label: 'Neural Access', icon: User },
    { id: 'storage', label: 'Data Retention', icon: Database },
    { id: 'ai', label: 'Model Registry', icon: Cpu },
    { id: 'network', label: 'Sector Routing', icon: Globe },
    { id: 'notifications', label: 'Alert Protocols', icon: Bell },
  ];

  // Fetch users for Neural Access tab
  const { data: users, isLoading: usersLoading } = useQuery({
    queryKey: ['users'],
    queryFn: usersAPI.getUsers,
    retry: false, // Don't retry if it fails (e.g., if user is not admin)
  });

  const handleSave = () => {
    toast.success('System configuration synchronized', {
      style: { background: '#121214', color: '#fff', border: '1px solid #262626' }
    });
  };

  const handleNuclearReset = () => {
    toast.error('ACCESS DENIED: Nuclear reset requires biometric authentication.', {
      icon: '🔒',
      style: { background: '#3f0000', color: '#fff', border: '1px solid #ff0000' }
    });
  };

  return (
    <div className="h-screen bg-[#0a0a0c] text-neutral-200 flex flex-col overflow-hidden">
      <div className="p-8 flex-1 flex flex-col min-h-0">
        <header className="mb-10 shrink-0">
          <div className="flex items-center space-x-4 mb-2">
            <div className="p-3 bg-white/5 rounded-2xl border border-white/10">
              <SettingsIcon className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-3xl font-black uppercase tracking-tighter text-white">System Command Center</h1>
          </div>
          <p className="text-[10px] font-black uppercase tracking-[0.3em] text-neutral-500">
            Advanced System Orchestration &bull; Environment v3.1.2-ALPHA
          </p>
        </header>

        <div className="flex-1 flex space-x-8 min-h-0 overflow-hidden">
          {/* ── Category Sidebar ── */}
          <div className="w-72 flex flex-col space-y-2 shrink-0">
            {categories.map(cat => (
              <button
                key={cat.id}
                onClick={() => setActiveCategory(cat.id)}
                className={`flex items-center justify-between p-4 rounded-2xl border transition-all group ${
                  activeCategory === cat.id 
                    ? 'bg-blue-600 border-blue-500 text-white shadow-xl shadow-blue-600/20' 
                    : 'bg-white/5 border-white/5 text-neutral-500 hover:bg-white/10'
                }`}
              >
                <div className="flex items-center space-x-4">
                  <cat.icon className={`w-4 h-4 ${activeCategory === cat.id ? 'text-white' : 'text-neutral-500 group-hover:text-white'}`} />
                  <span className="text-[10px] font-black uppercase tracking-widest">{cat.label}</span>
                </div>
                <ChevronRight className={`w-3 h-3 ${activeCategory === cat.id ? 'text-white' : 'text-neutral-700'}`} />
              </button>
            ))}
            
            <div className="mt-auto p-6 bg-red-600/5 border border-red-500/10 rounded-3xl cursor-pointer hover:bg-red-600/10 transition-colors" onClick={handleNuclearReset}>
               <Lock className="w-5 h-5 text-red-500 mb-3" />
               <p className="text-[9px] font-black text-red-400 uppercase tracking-widest mb-1">Danger Zone</p>
               <button className="text-[10px] font-black text-white uppercase hover:underline">Nuclear Reset</button>
            </div>
          </div>

          {/* ── Content Area ── */}
          <div className="flex-1 bg-neutral-900/30 border border-white/5 rounded-[40px] flex flex-col overflow-hidden">
            <div className="p-10 flex-1 overflow-y-auto custom-scrollbar">
              
              {/* ── 1. Tactical Config (General) ── */}
              {activeCategory === 'general' && (
                <div className="max-w-2xl space-y-10 animate-in fade-in slide-in-from-right-4">
                  <section>
                    <h3 className="text-sm font-black text-white uppercase tracking-widest mb-6 flex items-center">
                      <span className="w-1.5 h-1.5 bg-blue-500 rounded-full mr-3" />
                      Platform Identity
                    </h3>
                    <div className="grid grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <label className="text-[10px] font-black text-neutral-600 uppercase tracking-[0.2em]">Deployment Name</label>
                        <input className="w-full bg-black/50 border border-white/5 rounded-2xl p-4 text-xs font-bold text-white focus:ring-1 ring-blue-500 outline-none" defaultValue="NEXUS-7 PROXY" />
                      </div>
                      <div className="space-y-2">
                        <label className="text-[10px] font-black text-neutral-600 uppercase tracking-[0.2em]">Strategic Location</label>
                        <input className="w-full bg-black/50 border border-white/5 rounded-2xl p-4 text-xs font-bold text-white focus:ring-1 ring-blue-500 outline-none" defaultValue="SECTOR-G7" />
                      </div>
                    </div>
                  </section>

                  <section>
                    <h3 className="text-sm font-black text-white uppercase tracking-widest mb-6 flex items-center">
                      <span className="w-1.5 h-1.5 bg-yellow-500 rounded-full mr-3" />
                      Hardware Acceleration
                    </h3>
                    <div className="p-6 bg-white/5 border border-white/5 rounded-3xl space-y-6">
                       <div className="flex items-center justify-between cursor-pointer">
                          <div>
                             <p className="text-xs font-bold text-white uppercase tracking-tight">Enable TensorCore Offload</p>
                             <p className="text-[9px] font-black text-neutral-500 uppercase">Utilize NVIDIA discrete hardware for inference</p>
                          </div>
                          <div className="w-12 h-6 bg-blue-600 rounded-full relative">
                             <div className="absolute right-1 top-1 w-4 h-4 bg-white rounded-full shadow-lg" />
                          </div>
                       </div>
                       <div className="flex items-center justify-between cursor-pointer">
                          <div>
                             <p className="text-xs font-bold text-white uppercase tracking-tight">FP16 Mixed Precision</p>
                             <p className="text-[9px] font-black text-neutral-500 uppercase">Optimize throughput with negligible accuracy loss</p>
                          </div>
                          <div className="w-12 h-6 bg-white/10 rounded-full relative">
                             <div className="absolute left-1 top-1 w-4 h-4 bg-neutral-600 rounded-full" />
                          </div>
                       </div>
                    </div>
                  </section>
                </div>
              )}

              {/* ── 2. Neural Access (Users) ── */}
              {activeCategory === 'users' && (
                <div className="max-w-4xl space-y-8 animate-in fade-in slide-in-from-right-4">
                  <div className="flex justify-between items-center mb-6">
                    <h3 className="text-sm font-black text-white uppercase tracking-widest flex items-center">
                      <span className="w-1.5 h-1.5 bg-purple-500 rounded-full mr-3" />
                      Operator Privileges
                    </h3>
                    <button className="flex items-center space-x-2 px-4 py-2 bg-white/5 border border-white/10 hover:bg-white/10 rounded-xl text-[10px] font-black uppercase transition-colors">
                      <Plus className="w-3 h-3" />
                      <span>Add Operator</span>
                    </button>
                  </div>
                  
                  <div className="bg-white/5 border border-white/5 rounded-3xl overflow-hidden">
                    <table className="w-full text-left">
                      <thead className="bg-black/40 text-[9px] font-black uppercase tracking-widest text-neutral-500">
                        <tr>
                          <th className="p-4 pl-6">Operator ID</th>
                          <th className="p-4">Clearance Level</th>
                          <th className="p-4">Status</th>
                          <th className="p-4 text-right pr-6">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {usersLoading ? (
                          <tr><td colSpan="4" className="p-8 text-center text-neutral-500">Loading directory...</td></tr>
                        ) : users && users.length > 0 ? (
                          users.map(user => (
                            <tr key={user.id} className="hover:bg-white/5 transition-colors">
                              <td className="p-4 pl-6">
                                <div className="flex items-center space-x-3">
                                  <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-600 to-purple-600 flex items-center justify-center text-xs font-bold text-white">
                                    {user.username.substring(0, 2).toUpperCase()}
                                  </div>
                                  <div>
                                    <p className="text-xs font-bold text-white">{user.username}</p>
                                    <p className="text-[10px] text-neutral-500 font-mono">{user.email}</p>
                                  </div>
                                </div>
                              </td>
                              <td className="p-4">
                                <span className={`px-2 py-1 rounded-md text-[9px] font-black uppercase ${user.role === 'admin' ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'bg-blue-500/20 text-blue-400 border border-blue-500/30'}`}>
                                  {user.role}
                                </span>
                              </td>
                              <td className="p-4">
                                <span className="flex items-center space-x-1.5 text-[10px] font-bold text-green-400">
                                  <span className="w-1.5 h-1.5 bg-green-500 rounded-full"></span>
                                  <span>Active</span>
                                </span>
                              </td>
                              <td className="p-4 text-right pr-6">
                                <button className="p-2 hover:bg-white/10 rounded-lg text-neutral-500 hover:text-red-400 transition-colors">
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              </td>
                            </tr>
                          ))
                        ) : (
                          // Fallback UI if not admin
                          <tr className="hover:bg-white/5 transition-colors">
                            <td className="p-4 pl-6">
                              <div className="flex items-center space-x-3">
                                <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-600 to-purple-600 flex items-center justify-center text-xs font-bold text-white">
                                  AD
                                </div>
                                <div>
                                  <p className="text-xs font-bold text-white">admin</p>
                                  <p className="text-[10px] text-neutral-500 font-mono">admin@nexus.system</p>
                                </div>
                              </div>
                            </td>
                            <td className="p-4">
                              <span className="px-2 py-1 rounded-md text-[9px] font-black uppercase bg-red-500/20 text-red-400 border border-red-500/30">
                                ADMIN
                              </span>
                            </td>
                            <td className="p-4">
                              <span className="flex items-center space-x-1.5 text-[10px] font-bold text-green-400">
                                <span className="w-1.5 h-1.5 bg-green-500 rounded-full"></span>
                                <span>Active</span>
                              </span>
                            </td>
                            <td className="p-4 text-right pr-6">
                              <button className="p-2 hover:bg-white/10 rounded-lg text-neutral-500 hover:text-red-400 transition-colors">
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* ── 3. Data Retention (Storage) ── */}
              {activeCategory === 'storage' && (
                <div className="max-w-2xl space-y-10 animate-in fade-in slide-in-from-right-4">
                  <section>
                    <h3 className="text-sm font-black text-white uppercase tracking-widest mb-6 flex items-center">
                      <span className="w-1.5 h-1.5 bg-teal-500 rounded-full mr-3" />
                      Archive Policies
                    </h3>
                    <div className="space-y-6 p-6 bg-white/5 border border-white/5 rounded-3xl">
                      <div className="space-y-4">
                        <div className="flex justify-between items-end">
                          <label className="text-[10px] font-black text-neutral-400 uppercase tracking-widest">Event Footage Retention</label>
                          <span className="text-xl font-black text-white">{retentionDays} Days</span>
                        </div>
                        <input 
                          type="range" 
                          min="1" max="90" 
                          value={retentionDays}
                          onChange={(e) => setRetentionDays(e.target.value)}
                          className="w-full h-2 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-blue-500" 
                        />
                        <div className="flex justify-between text-[8px] font-bold text-neutral-600 uppercase">
                          <span>1 Day</span>
                          <span>90 Days</span>
                        </div>
                      </div>
                    </div>
                  </section>

                  <section>
                    <h3 className="text-sm font-black text-white uppercase tracking-widest mb-6 flex items-center">
                      <span className="w-1.5 h-1.5 bg-orange-500 rounded-full mr-3" />
                      Database Maintenance
                    </h3>
                    <div className="p-6 bg-white/5 border border-white/5 rounded-3xl space-y-6">
                       <div className="flex items-center justify-between cursor-pointer" onClick={() => setAutoPrune(!autoPrune)}>
                          <div>
                             <p className="text-xs font-bold text-white uppercase tracking-tight">Auto-Prune Telemetry</p>
                             <p className="text-[9px] font-black text-neutral-500 uppercase">Automatically delete non-critical logs older than 7 days</p>
                          </div>
                          <div className={`w-12 h-6 rounded-full relative transition-colors ${autoPrune ? 'bg-blue-600' : 'bg-white/10'}`}>
                             <div className={`absolute top-1 w-4 h-4 rounded-full transition-all ${autoPrune ? 'bg-white right-1 shadow-lg' : 'bg-neutral-600 left-1'}`} />
                          </div>
                       </div>
                    </div>
                  </section>
                </div>
              )}

              {/* ── 4. Model Registry (AI) ── */}
              {activeCategory === 'ai' && (
                <div className="max-w-3xl space-y-8 animate-in fade-in slide-in-from-right-4">
                  <h3 className="text-sm font-black text-white uppercase tracking-widest mb-6 flex items-center">
                    <span className="w-1.5 h-1.5 bg-pink-500 rounded-full mr-3" />
                    Active Inference Pipelines
                  </h3>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* YOLO Model */}
                    <div className="p-6 bg-gradient-to-br from-white/5 to-white/[0.02] border border-white/10 rounded-3xl relative overflow-hidden group">
                      <div className="absolute top-0 right-0 p-4">
                        <div className={`w-12 h-6 rounded-full relative cursor-pointer transition-colors ${activeModels.yolo ? 'bg-blue-600' : 'bg-white/10'}`} onClick={() => setActiveModels(s => ({...s, yolo: !s.yolo}))}>
                           <div className={`absolute top-1 w-4 h-4 rounded-full transition-all ${activeModels.yolo ? 'bg-white right-1 shadow-lg' : 'bg-neutral-600 left-1'}`} />
                        </div>
                      </div>
                      <Cpu className="w-8 h-8 text-blue-400 mb-4" />
                      <h4 className="text-lg font-black text-white mb-1">YOLOv8x-Sec</h4>
                      <p className="text-[10px] text-neutral-400 font-bold uppercase tracking-widest mb-4">Primary RGB Object Detection</p>
                      <div className="flex space-x-2">
                        <span className="px-2 py-1 bg-black/50 border border-white/10 rounded text-[9px] font-black text-neutral-300">80 CLASSES</span>
                        <span className="px-2 py-1 bg-black/50 border border-white/10 rounded text-[9px] font-black text-neutral-300">GPU OPTIMIZED</span>
                      </div>
                    </div>

                    {/* Thermal Model */}
                    <div className="p-6 bg-gradient-to-br from-white/5 to-white/[0.02] border border-white/10 rounded-3xl relative overflow-hidden group">
                      <div className="absolute top-0 right-0 p-4">
                        <div className={`w-12 h-6 rounded-full relative cursor-pointer transition-colors ${activeModels.thermal ? 'bg-blue-600' : 'bg-white/10'}`} onClick={() => setActiveModels(s => ({...s, thermal: !s.thermal}))}>
                           <div className={`absolute top-1 w-4 h-4 rounded-full transition-all ${activeModels.thermal ? 'bg-white right-1 shadow-lg' : 'bg-neutral-600 left-1'}`} />
                        </div>
                      </div>
                      <Activity className="w-8 h-8 text-orange-400 mb-4" />
                      <h4 className="text-lg font-black text-white mb-1">ThermNet-V2</h4>
                      <p className="text-[10px] text-neutral-400 font-bold uppercase tracking-widest mb-4">Thermal Signature Analysis</p>
                      <div className="flex space-x-2">
                        <span className="px-2 py-1 bg-black/50 border border-white/10 rounded text-[9px] font-black text-neutral-300">NIGHT VISION</span>
                        <span className="px-2 py-1 bg-black/50 border border-white/10 rounded text-[9px] font-black text-neutral-300">LONG RANGE</span>
                      </div>
                    </div>

                    {/* Face Model */}
                    <div className="p-6 bg-gradient-to-br from-white/5 to-white/[0.02] border border-white/10 rounded-3xl relative overflow-hidden group opacity-50">
                      <div className="absolute top-0 right-0 p-4">
                        <div className={`w-12 h-6 rounded-full relative cursor-pointer transition-colors ${activeModels.face ? 'bg-blue-600' : 'bg-white/10'}`} onClick={() => setActiveModels(s => ({...s, face: !s.face}))}>
                           <div className={`absolute top-1 w-4 h-4 rounded-full transition-all ${activeModels.face ? 'bg-white right-1 shadow-lg' : 'bg-neutral-600 left-1'}`} />
                        </div>
                      </div>
                      <User className="w-8 h-8 text-neutral-500 mb-4" />
                      <h4 className="text-lg font-black text-white mb-1">FaceID-ResNet</h4>
                      <p className="text-[10px] text-neutral-400 font-bold uppercase tracking-widest mb-4">Biometric Verification</p>
                      <div className="flex space-x-2">
                        <span className="px-2 py-1 bg-black/50 border border-white/10 rounded text-[9px] font-black text-red-400 border-red-500/30">LICENSE REQ</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* ── 5. Sector Routing (Network) ── */}
              {activeCategory === 'network' && (
                <div className="max-w-2xl space-y-10 animate-in fade-in slide-in-from-right-4">
                  <section>
                    <h3 className="text-sm font-black text-white uppercase tracking-widest mb-6 flex items-center">
                      <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full mr-3" />
                      Stream Gateway
                    </h3>
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <label className="text-[10px] font-black text-neutral-600 uppercase tracking-[0.2em]">RTSP Proxy URL</label>
                        <div className="flex items-center bg-black/50 border border-white/5 rounded-2xl p-4">
                          <Network className="w-4 h-4 text-neutral-500 mr-3" />
                          <input className="w-full bg-transparent text-xs font-bold text-white outline-none" defaultValue="rtsp://10.0.0.5:8554/stream" />
                        </div>
                      </div>
                      <div className="space-y-2">
                        <label className="text-[10px] font-black text-neutral-600 uppercase tracking-[0.2em]">WebRTC STUN/TURN Server</label>
                        <div className="flex items-center bg-black/50 border border-white/5 rounded-2xl p-4">
                          <Server className="w-4 h-4 text-neutral-500 mr-3" />
                          <input className="w-full bg-transparent text-xs font-bold text-white outline-none" defaultValue="stun:stun.l.google.com:19302" />
                        </div>
                      </div>
                    </div>
                  </section>
                </div>
              )}

              {/* ── 6. Alert Protocols (Notifications) ── */}
              {activeCategory === 'notifications' && (
                <div className="max-w-2xl space-y-10 animate-in fade-in slide-in-from-right-4">
                  <section>
                    <h3 className="text-sm font-black text-white uppercase tracking-widest mb-6 flex items-center">
                      <span className="w-1.5 h-1.5 bg-red-500 rounded-full mr-3" />
                      Notification Channels
                    </h3>
                    <div className="p-6 bg-white/5 border border-white/5 rounded-3xl space-y-6">
                       <div className="flex items-center justify-between cursor-pointer" onClick={() => setNotifications(s => ({...s, email: !s.email}))}>
                          <div>
                             <p className="text-xs font-bold text-white uppercase tracking-tight">Encrypted Email Digests</p>
                             <p className="text-[9px] font-black text-neutral-500 uppercase">Send daily summaries and critical alerts to administrators</p>
                          </div>
                          <div className={`w-12 h-6 rounded-full relative transition-colors ${notifications.email ? 'bg-blue-600' : 'bg-white/10'}`}>
                             <div className={`absolute top-1 w-4 h-4 rounded-full transition-all ${notifications.email ? 'bg-white right-1 shadow-lg' : 'bg-neutral-600 left-1'}`} />
                          </div>
                       </div>
                       <div className="flex items-center justify-between cursor-pointer" onClick={() => setNotifications(s => ({...s, push: !s.push}))}>
                          <div>
                             <p className="text-xs font-bold text-white uppercase tracking-tight">Dashboard Push Alerts</p>
                             <p className="text-[9px] font-black text-neutral-500 uppercase">Real-time browser notifications for intrusion events</p>
                          </div>
                          <div className={`w-12 h-6 rounded-full relative transition-colors ${notifications.push ? 'bg-blue-600' : 'bg-white/10'}`}>
                             <div className={`absolute top-1 w-4 h-4 rounded-full transition-all ${notifications.push ? 'bg-white right-1 shadow-lg' : 'bg-neutral-600 left-1'}`} />
                          </div>
                       </div>
                       <div className="flex items-center justify-between cursor-pointer" onClick={() => setNotifications(s => ({...s, sms: !s.sms}))}>
                          <div>
                             <p className="text-xs font-bold text-white uppercase tracking-tight">SMS Dispatch</p>
                             <p className="text-[9px] font-black text-neutral-500 uppercase">Direct mobile alerts for Critical severity events</p>
                          </div>
                          <div className={`w-12 h-6 rounded-full relative transition-colors ${notifications.sms ? 'bg-blue-600' : 'bg-white/10'}`}>
                             <div className={`absolute top-1 w-4 h-4 rounded-full transition-all ${notifications.sms ? 'bg-white right-1 shadow-lg' : 'bg-neutral-600 left-1'}`} />
                          </div>
                       </div>
                    </div>
                  </section>

                  <section>
                    <h3 className="text-sm font-black text-white uppercase tracking-widest mb-6 flex items-center">
                      <span className="w-1.5 h-1.5 bg-yellow-500 rounded-full mr-3" />
                      External Webhooks
                    </h3>
                    <div className="space-y-2">
                      <label className="text-[10px] font-black text-neutral-600 uppercase tracking-[0.2em]">Slack / Discord Integration URL</label>
                      <input 
                        value={webhooks}
                        onChange={(e) => setWebhooks(e.target.value)}
                        className="w-full bg-black/50 border border-white/5 rounded-2xl p-4 text-xs font-bold text-neutral-400 focus:ring-1 ring-blue-500 outline-none" 
                      />
                    </div>
                  </section>
                </div>
              )}

            </div>

            <footer className="p-8 bg-black/40 border-t border-white/5 flex justify-between items-center">
               <div className="flex items-center space-x-2 text-[9px] font-black text-neutral-600 uppercase tracking-widest">
                  <Shield className="w-3 h-3" />
                  <span>Encrypted session active</span>
               </div>
               <div className="flex space-x-4">
                  <button className="px-8 py-3 bg-white/5 text-neutral-500 text-[10px] font-black uppercase tracking-widest rounded-xl hover:bg-white/10 transition-all">Revert Changes</button>
                  <button 
                    onClick={handleSave}
                    className="flex items-center space-x-3 px-10 py-3 bg-blue-600 text-white text-[10px] font-black uppercase tracking-widest rounded-xl shadow-xl shadow-blue-600/20 hover:bg-blue-500 transition-all active:scale-95"
                  >
                    <Save className="w-3 h-3" />
                    <span>Synchronize Config</span>
                  </button>
               </div>
            </footer>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Settings;
