import React, { useState } from 'react';
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
  ChevronRight
} from 'lucide-react';
import toast from 'react-hot-toast';

const Settings = () => {
  const [activeCategory, setActiveCategory] = useState('general');

  const categories = [
    { id: 'general', label: 'Tactical Config', icon: SettingsIcon },
    { id: 'users', label: 'Neural Access', icon: User },
    { id: 'storage', label: 'Data Retention', icon: Database },
    { id: 'ai', label: 'Model Registry', icon: Cpu },
    { id: 'network', label: 'Sector Routing', icon: Globe },
    { id: 'notifications', label: 'Alert Protocols', icon: Bell },
  ];

  const handleSave = () => {
    toast.success('System configuration synchronized', {
      style: { background: '#121214', color: '#fff', border: '1px solid #262626' }
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
            
            <div className="mt-auto p-6 bg-red-600/5 border border-red-500/10 rounded-3xl">
               <Lock className="w-5 h-5 text-red-500 mb-3" />
               <p className="text-[9px] font-black text-red-400 uppercase tracking-widest mb-1">Danger Zone</p>
               <button className="text-[10px] font-black text-white uppercase hover:underline">Nuclear Reset</button>
            </div>
          </div>

          {/* ── Content Area ── */}
          <div className="flex-1 bg-neutral-900/30 border border-white/5 rounded-[40px] flex flex-col overflow-hidden">
            <div className="p-10 flex-1 overflow-y-auto custom-scrollbar">
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
                        <input className="w-full bg-black/50 border border-white/5 rounded-2xl p-4 text-xs font-bold text-white focus:ring-1 ring-blue-500 outline-none" placeholder="NEXUS-7 PROXY" />
                      </div>
                      <div className="space-y-2">
                        <label className="text-[10px] font-black text-neutral-600 uppercase tracking-[0.2em]">Strategic Location</label>
                        <input className="w-full bg-black/50 border border-white/5 rounded-2xl p-4 text-xs font-bold text-white focus:ring-1 ring-blue-500 outline-none" placeholder="SECTOR-G7" />
                      </div>
                    </div>
                  </section>

                  <section>
                    <h3 className="text-sm font-black text-white uppercase tracking-widest mb-6 flex items-center">
                      <span className="w-1.5 h-1.5 bg-yellow-500 rounded-full mr-3" />
                      Hardware Acceleration
                    </h3>
                    <div className="p-6 bg-white/5 border border-white/5 rounded-3xl space-y-6">
                       <div className="flex items-center justify-between">
                          <div>
                             <p className="text-xs font-bold text-white uppercase tracking-tight">Enable TensorCore Offload</p>
                             <p className="text-[9px] font-black text-neutral-500 uppercase">Utilize NVIDIA discrete hardware for inference</p>
                          </div>
                          <div className="w-12 h-6 bg-blue-600 rounded-full relative">
                             <div className="absolute right-1 top-1 w-4 h-4 bg-white rounded-full shadow-lg" />
                          </div>
                       </div>
                       <div className="flex items-center justify-between">
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

                  <section>
                    <h3 className="text-sm font-black text-white uppercase tracking-widest mb-6 flex items-center">
                      <span className="w-1.5 h-1.5 bg-green-500 rounded-full mr-3" />
                      Visual Interface
                    </h3>
                    <div className="space-y-4">
                       <div className="flex items-center justify-between p-4 bg-white/5 rounded-2xl border border-white/5">
                          <span className="text-[10px] font-black uppercase text-neutral-400">Default Refresh Rate</span>
                          <span className="text-xs font-black text-white">60 FPS</span>
                       </div>
                       <div className="flex items-center justify-between p-4 bg-white/5 rounded-2xl border border-white/5">
                          <span className="text-[10px] font-black uppercase text-neutral-400">Stream Protocol</span>
                          <span className="text-xs font-black text-white">WebRTC / H.264</span>
                       </div>
                    </div>
                  </section>
                </div>
              )}

              {activeCategory !== 'general' && (
                <div className="flex flex-col items-center justify-center h-full space-y-4 opacity-50">
                   <div className="p-6 bg-white/5 rounded-full border border-white/10">
                      <RefreshCw className="w-8 h-8 text-neutral-500 animate-spin" />
                   </div>
                   <p className="text-[10px] font-black uppercase tracking-widest text-neutral-600">Reconfiguring Sub-module Interface...</p>
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
