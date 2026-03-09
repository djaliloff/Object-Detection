import React, { useState, useEffect, useRef } from 'react';
import { 
  Shield, 
  Settings, 
  Activity, 
  Bell, 
  Camera, 
  LayoutDashboard, 
  Search, 
  User,
  AlertTriangle,
  CheckCircle,
  Menu,
  ChevronRight
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  AreaChart,
  Area
} from 'recharts';

const dummyData = [
  { time: '00:00', detections: 2 },
  { time: '04:00', detections: 1 },
  { time: '08:00', detections: 5 },
  { time: '12:00', detections: 12 },
  { time: '16:00', detections: 8 },
  { time: '20:00', detections: 15 },
  { time: '23:59', detections: 4 },
];

const App = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [notifications, setNotifications] = useState([]);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  // Simulate incoming WebSocket notifications
  useEffect(() => {
    const interval = setInterval(() => {
      const types = ['intrusion', 'loitering', 'motion'];
      const severity = ['critical', 'warning', 'info'];
      const newAlert = {
        id: Date.now(),
        type: types[Math.floor(Math.random() * types.length)],
        status: severity[Math.floor(Math.random() * severity.length)],
        timestamp: new Date().toLocaleTimeString(),
        location: 'Zone A - East Entrance'
      };
      setNotifications(prev => [newAlert, ...prev].slice(0, 5));
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex h-screen bg-background font-sans overflow-hidden">
      {/* --- Sidebar --- */}
      <aside className={`glass z-20 transition-all duration-300 ${isSidebarOpen ? 'w-64' : 'w-20'} flex flex-col`}>
        <div className="p-6 flex items-center gap-3">
          <div className="bg-primary p-2 rounded-lg">
            <Shield className="text-white h-6 w-6" />
          </div>
          {isSidebarOpen && <span className="font-bold text-xl tracking-tight">KAVACH</span>}
        </div>

        <nav className="flex-1 mt-6">
          <NavItem icon={<LayoutDashboard size={22}/>} label="Dashboard" active={activeTab === 'dashboard'} onClick={() => setActiveTab('dashboard')} open={isSidebarOpen} />
          <NavItem icon={<Camera size={22}/>} label="Live Cameras" active={activeTab === 'cameras'} onClick={() => setActiveTab('cameras')} open={isSidebarOpen} />
          <NavItem icon={<Activity size={22}/>} label="Analytics" active={activeTab === 'analytics'} onClick={() => setActiveTab('analytics')} open={isSidebarOpen} />
          <NavItem icon={<Bell size={22}/>} label="Alerts" active={activeTab === 'alerts'} onClick={() => setActiveTab('alerts')} open={isSidebarOpen} />
        </nav>

        <div className="p-4 border-t border-border">
          <NavItem icon={<Settings size={22}/>} label="Settings" active={activeTab === 'settings'} onClick={() => setActiveTab('settings')} open={isSidebarOpen} />
        </div>
      </aside>

      {/* --- Main Content --- */}
      <main className="flex-1 flex flex-col overflow-y-auto">
        {/* Header */}
        <header className="h-20 glass flex items-center justify-between px-8 border-b border-border sticky top-0 z-10">
          <div className="flex items-center gap-4">
             <button onClick={() => setIsSidebarOpen(!isSidebarOpen)} className="p-2 hover:bg-white/5 rounded-lg transition-colors">
                <Menu size={20} />
             </button>
             <h2 className="text-lg font-medium capitalize prose-sky prose">{activeTab}</h2>
          </div>
          
          <div className="flex items-center gap-6">
            <div className="relative group">
              <input 
                type="text" 
                placeholder="Search events..." 
                className="bg-surface border border-border rounded-full py-2 pl-10 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 w-64 transition-all"
              />
              <Search className="absolute left-3 top-2.5 text-white/30" size={16} />
            </div>
            <div className="flex items-center gap-3">
              <div className="text-right">
                <div className="text-sm font-medium">Administrator</div>
                <div className="text-[10px] text-white/40">Secure Status: Valid</div>
              </div>
              <div className="h-10 w-10 rounded-full bg-gradient-to-br from-primary to-primary-dark flex items-center justify-center border-2 border-white/10">
                <User size={20} />
              </div>
            </div>
          </div>
        </header>

        {/* Dashboard Content */}
        <div className="p-8 space-y-8">
          {/* Stats Bar */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <StatCard label="Total Detections" value="2,482" delta="+12%" icon={<Activity className="text-primary"/>}/>
            <StatCard label="Critical Alerts" value="24" delta="+2" icon={<AlertTriangle className="text-danger"/>}/>
            <StatCard label="Online Sources" value="12/12" delta="100%" icon={<CheckCircle className="text-success"/>}/>
            <StatCard label="Storage Status" value="74%" delta="2.4TB" icon={<Shield className="text-warning"/>}/>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Live Camera Feed Slot */}
            <div className="lg:col-span-2 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xl font-semibold flex items-center gap-2">
                  <Camera size={20} className="text-primary"/>
                  Main Entrance - High Definition 
                </h3>
                <span className="flex items-center gap-2 text-xs bg-danger/20 text-danger border border-danger/30 rounded-full px-3 py-1 animate-pulse">
                  <div className="h-1.5 w-1.5 rounded-full bg-danger"></div>
                  LIVE
                </span>
              </div>
              
              <div className="aspect-video glass rounded-2xl overflow-hidden relative group">
                  <img src="https://images.unsplash.com/photo-1557597774-9d2739f85a94?auto=format&fit=crop&q=80&w=1200" alt="CCTV Feed" className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity duration-700"/>
                  
                  {/* AI Detection Overlays Placeholder */}
                  <div className="absolute top-1/4 left-1/3 w-32 h-64 border-2 border-primary rounded shadow-[0_0_15px_rgba(14,165,233,0.5)] flex flex-col justify-end">
                      <div className="bg-primary text-[10px] px-1 py-0.5 text-white font-bold uppercase tracking-wider">Person 0.98</div>
                  </div>

                  <div className="absolute bottom-6 left-6 right-6 flex justify-between items-end pointer-events-none">
                    <div className="text-white/60 text-[10px] font-mono p-2 glass rounded">
                       LATENCY: 42ms<br/>
                       FPS: 30.2<br/>
                       BUFFER: 0.1s
                    </div>
                    <div className="flex gap-2 pointer-events-auto">
                        <button className="p-2 glass rounded-lg hover:bg-white/20 transition-colors"><Search size={16}/></button>
                        <button className="p-2 glass rounded-lg hover:bg-white/20 transition-colors text-danger"><Bell size={16}/></button>
                    </div>
                  </div>
              </div>
            </div>

            {/* Real-time Event Log */}
            <div className="space-y-4">
              <h3 className="text-xl font-semibold">Live Event Log</h3>
              <div className="space-y-3">
                <AnimatePresence initial={false}>
                  {notifications.map((alert) => (
                    <motion.div 
                      key={alert.id}
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      className={`p-4 rounded-xl border flex gap-4 ${
                        alert.status === 'critical' ? 'bg-danger/10 border-danger/30' : 
                        alert.status === 'warning' ? 'bg-warning/10 border-warning/30' : 
                        'bg-surface border-border'
                      }`}
                    >
                      <div className={`mt-1 h-2 w-2 rounded-full flex-shrink-0 ${
                        alert.status === 'critical' ? 'bg-danger shadow-[0_0_8px_#ef4444]' : 
                        alert.status === 'warning' ? 'bg-warning' : 'bg-primary'
                      }`}></div>
                      <div className="flex-1">
                        <div className="flex justify-between items-start">
                          <span className="text-sm font-bold uppercase tracking-wider">{alert.type} Detected</span>
                          <span className="text-[10px] text-white/40 font-mono">{alert.timestamp}</span>
                        </div>
                        <p className="text-xs text-white/60 mt-1">{alert.location}</p>
                        <button className="mt-2 text-[10px] font-bold text-primary flex items-center gap-1 group">
                          VIEW SNAPSHOT <ChevronRight size={10} className="group-hover:translate-x-1 transition-transform" />
                        </button>
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>
                <div className="text-center py-4 bg-surface/30 rounded-xl border border-dashed border-border text-xs text-white/30">
                  Waiting for new data stream...
                </div>
              </div>
            </div>
          </div>

          {/* Bottom Analytics Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="glass p-6 rounded-2xl h-80">
              <h3 className="text-lg font-medium mb-6">Activity Volume (24h)</h3>
              <ResponsiveContainer width="100%" height="85%">
                <AreaChart data={dummyData}>
                  <defs>
                    <linearGradient id="colorDetections" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f1f1f" vertical={false}/>
                  <XAxis dataKey="time" stroke="#444" fontSize={10} tickLine={false} axisLine={false}/>
                  <YAxis stroke="#444" fontSize={10} tickLine={false} axisLine={false}/>
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#121212', border: '1px solid #333', borderRadius: '8px' }}
                    itemStyle={{ color: '#0ea5e9' }}
                  />
                  <Area type="monotone" dataKey="detections" stroke="#0ea5e9" fillOpacity={1} fill="url(#colorDetections)" strokeWidth={3} />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            <div className="glass p-6 rounded-2xl overflow-hidden flex flex-col">
              <h3 className="text-lg font-medium mb-4">Thermal Fusion Status</h3>
              <div className="flex-1 flex flex-col justify-between gap-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-3 bg-white/5 rounded-xl">
                      <span className="text-[10px] text-white/40 uppercase font-bold tracking-widest">Confidence Gap</span>
                      <div className="text-2xl font-bold">14<span className="text-sm text-white/40">%</span></div>
                    </div>
                    <div className="p-3 bg-white/5 rounded-xl">
                      <span className="text-[10px] text-white/40 uppercase font-bold tracking-widest">Alignment Offset</span>
                      <div className="text-2xl font-bold">0.42<span className="text-sm text-white/40">px</span></div>
                    </div>
                  </div>
                  <div className="relative h-24 bg-surface rounded-xl border border-border overflow-hidden">
                     <div className="absolute inset-0 flex items-center justify-center">
                        <span className="text-xs text-white/20 uppercase tracking-[.3em] font-light">Cross-Modal Sync Map</span>
                     </div>
                     <div className="absolute right-0 top-0 bottom-0 w-1/4 bg-primary/20 blur-xl"></div>
                  </div>
                  <div className="text-[10px] text-primary bg-primary/10 p-2 rounded border border-primary/20 text-center">
                    AUTONOMOUS ILLUMINATION GATING ACTIVE
                  </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

const NavItem = ({ icon, label, active, onClick, open }) => (
  <button 
    onClick={onClick}
    className={`w-full flex items-center gap-4 px-6 py-4 transition-all relative group
      ${active ? 'text-primary' : 'text-white/50 hover:text-white hover:bg-white/5'}
    `}
  >
    {active && <motion.div layoutId="nav-active" className="absolute left-0 top-1 bottom-1 w-1 bg-primary rounded-r-full" />}
    <span className="transition-transform group-hover:scale-110 duration-200">{icon}</span>
    {open && <span className="text-sm font-medium">{label}</span>}
  </button>
);

const StatCard = ({ label, value, delta, icon }) => (
  <div className="glass p-6 rounded-2xl hover:border-primary/50 transition-colors group">
    <div className="flex justify-between items-start">
      <div className="bg-background/80 p-3 rounded-xl border border-border group-hover:bg-primary/5 transition-colors">
        {icon}
      </div>
      <span className="text-xs font-bold text-success bg-success/10 px-2 py-0.5 rounded-full">{delta}</span>
    </div>
    <div className="mt-4">
      <div className="text-2xl font-bold">{value}</div>
      <p className="text-white/40 text-xs mt-1 uppercase tracking-widest font-bold">{label}</p>
    </div>
  </div>
);

export default App;
