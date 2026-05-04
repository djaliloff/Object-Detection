import React from 'react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  AreaChart, 
  Area, 
  PieChart, 
  Pie, 
  Cell 
} from 'recharts';
import { 
  Activity, 
  TrendingUp, 
  Users, 
  Shield, 
  Zap,
  Target,
  Clock,
  ChevronRight
} from 'lucide-react';

const Analytics = () => {
  // Mock data for tactical visualization
  const hourlyData = [
    { time: '00:00', detections: 45, events: 2 },
    { time: '04:00', detections: 12, events: 1 },
    { time: '08:00', detections: 180, events: 8 },
    { time: '12:00', detections: 250, events: 12 },
    { time: '16:00', detections: 310, events: 15 },
    { time: '20:00', detections: 140, events: 5 },
    { time: '23:59', detections: 65, events: 3 },
  ];

  const classData = [
    { name: 'Person', value: 450, color: '#3b82f6' },
    { name: 'Vehicle', value: 320, color: '#10b981' },
    { name: 'Bag', value: 120, color: '#f59e0b' },
    { name: 'Unidentified', value: 45, color: '#ef4444' },
  ];

  const sectorPerformance = [
    { sector: 'Sector 1', accuracy: 98.2, alerts: 12 },
    { sector: 'Sector 2', accuracy: 94.5, alerts: 8 },
    { sector: 'Sector 3', accuracy: 99.1, alerts: 24 },
    { sector: 'Sector 4', accuracy: 89.8, alerts: 5 },
  ];

  const StatCard = ({ title, value, subvalue, icon: Icon, trend }) => (
    <div className="bg-neutral-900/50 border border-white/5 p-6 rounded-[32px] hover:border-blue-500/30 transition-all group">
      <div className="flex justify-between items-start mb-4">
        <div className="p-3 bg-white/5 rounded-2xl group-hover:bg-blue-600/20 transition-colors">
          <Icon className="w-5 h-5 text-neutral-400 group-hover:text-blue-400" />
        </div>
        {trend && (
          <span className={`text-[10px] font-black px-2 py-1 rounded-lg ${trend > 0 ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
            {trend > 0 ? '+' : ''}{trend}%
          </span>
        )}
      </div>
      <p className="text-[10px] font-black uppercase tracking-widest text-neutral-500 mb-1">{title}</p>
      <div className="flex items-baseline space-x-2">
        <h3 className="text-2xl font-black text-white">{value}</h3>
        <span className="text-[10px] font-bold text-neutral-600 uppercase">{subvalue}</span>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#0a0a0c] text-neutral-200 p-8">
      <header className="mb-10">
        <div className="flex items-center space-x-4 mb-2">
          <div className="p-3 bg-blue-600/20 rounded-2xl border border-blue-500/30">
            <TrendingUp className="w-6 h-6 text-blue-500" />
          </div>
          <h1 className="text-3xl font-black uppercase tracking-tighter text-white">Neural Intelligence Dashboard</h1>
        </div>
        <p className="text-[10px] font-black uppercase tracking-[0.3em] text-neutral-500">
          Aggregated Analytics & Performance Telemetry &bull; Phase 1 deployment
        </p>
      </header>

      {/* ── Top Row Stats ── */}
      <div className="grid grid-cols-4 gap-6 mb-8">
        <StatCard title="Total Detections" value="12,458" subvalue="Last 24h" icon={Target} trend={12.5} />
        <StatCard title="Neural Confidence" value="94.2%" subvalue="Average" icon={Zap} trend={0.8} />
        <StatCard title="Active Objects" value="42" subvalue="Current" icon={Users} />
        <StatCard title="System Uptime" value="99.9%" subvalue="Network" icon={Shield} />
      </div>

      <div className="grid grid-cols-12 gap-8">
        {/* ── Main Chart: Temporal Density ── */}
        <div className="col-span-8 bg-neutral-900/30 border border-white/5 rounded-[40px] p-8">
          <div className="flex justify-between items-center mb-8">
            <div>
              <h3 className="text-lg font-black text-white uppercase tracking-tight">Temporal Detection Density</h3>
              <p className="text-[10px] font-bold text-neutral-500 uppercase tracking-widest">Inference load across 24-hour cycle</p>
            </div>
            <div className="flex space-x-2">
              <button className="px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-[10px] font-black uppercase tracking-widest hover:bg-white/10 transition-all">24H</button>
              <button className="px-4 py-2 bg-blue-600 text-white rounded-xl text-[10px] font-black uppercase tracking-widest shadow-lg shadow-blue-500/20">7D</button>
            </div>
          </div>
          
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={hourlyData}>
                <defs>
                  <linearGradient id="colorDet" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                <XAxis 
                  dataKey="time" 
                  stroke="#ffffff20" 
                  fontSize={10} 
                  tickLine={false} 
                  axisLine={false}
                  tick={{fontWeight: '900', fill: '#666'}}
                />
                <YAxis 
                  stroke="#ffffff20" 
                  fontSize={10} 
                  tickLine={false} 
                  axisLine={false}
                  tick={{fontWeight: '900', fill: '#666'}}
                />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#121214', border: '1px solid #ffffff10', borderRadius: '16px' }}
                  itemStyle={{ fontSize: '10px', fontWeight: '900', textTransform: 'uppercase' }}
                />
                <Area type="monotone" dataKey="detections" stroke="#3b82f6" strokeWidth={4} fillOpacity={1} fill="url(#colorDet)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* ── Classification Distribution ── */}
        <div className="col-span-4 bg-neutral-900/30 border border-white/5 rounded-[40px] p-8">
          <h3 className="text-lg font-black text-white uppercase tracking-tight mb-2">Neural Classification</h3>
          <p className="text-[10px] font-bold text-neutral-500 uppercase tracking-widest mb-8">Object distribution by class</p>
          
          <div className="h-64 w-full relative">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={classData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={8}
                  dataKey="value"
                >
                  {classData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} stroke="none" />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <span className="text-2xl font-black text-white">935</span>
              <span className="text-[8px] font-black text-neutral-500 uppercase">Total Items</span>
            </div>
          </div>

          <div className="mt-6 space-y-3">
            {classData.map((item) => (
              <div key={item.name} className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <div className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }} />
                  <span className="text-[10px] font-black uppercase text-neutral-400">{item.name}</span>
                </div>
                <span className="text-xs font-black text-white">{item.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* ── Sector Performance ── */}
        <div className="col-span-12 bg-neutral-900/30 border border-white/5 rounded-[40px] p-8">
           <div className="flex items-center justify-between mb-8">
              <div>
                <h3 className="text-lg font-black text-white uppercase tracking-tight">Sector Performance Analytics</h3>
                <p className="text-[10px] font-bold text-neutral-500 uppercase tracking-widest">Hardware acceleration and accuracy per sector</p>
              </div>
              <Activity className="w-5 h-5 text-blue-500 opacity-50" />
           </div>

           <div className="grid grid-cols-4 gap-8">
              {sectorPerformance.map((sector) => (
                <div key={sector.sector} className="p-6 bg-white/5 rounded-[32px] border border-white/5 hover:border-blue-500/20 transition-all">
                   <div className="flex justify-between items-center mb-4">
                      <span className="text-[10px] font-black text-white uppercase tracking-widest">{sector.sector}</span>
                      <ChevronRight className="w-4 h-4 text-neutral-700" />
                   </div>
                   <div className="flex items-baseline space-x-2 mb-4">
                      <span className="text-3xl font-black text-white">{sector.accuracy}%</span>
                      <span className="text-[8px] font-bold text-neutral-500 uppercase">Accuracy</span>
                   </div>
                   <div className="space-y-2">
                      <div className="flex justify-between text-[8px] font-black uppercase">
                         <span className="text-neutral-500">Alert Frequency</span>
                         <span className="text-blue-400">{sector.alerts} EV/H</span>
                      </div>
                      <div className="w-full bg-white/5 h-1 rounded-full overflow-hidden">
                         <div className="bg-blue-500 h-full" style={{ width: `${sector.accuracy}%` }} />
                      </div>
                   </div>
                </div>
              ))}
           </div>
        </div>
      </div>
    </div>
  );
};

export default Analytics;
