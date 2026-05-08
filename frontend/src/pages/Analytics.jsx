import React, { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
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
import { eventsAPI, analyticsAPI } from '../utils/api';

const Analytics = () => {
  // Fetch real analytics summary
  const { data: analytics, isLoading: analyticsLoading } = useQuery({
    queryKey: ['analytics-summary'],
    queryFn: analyticsAPI.getSummary,
    refetchInterval: 30000,
    retry: false,
  });

  // Fetch real events for aggregation
  const { data: events } = useQuery({
    queryKey: ['analytics-events'],
    queryFn: () => eventsAPI.getEvents({ limit: 1000 }),
    refetchInterval: 30000,
    retry: false,
  });

  const { hourlyData, classData, totalClassified } = useMemo(() => {
    if (!events || !Array.isArray(events)) {
      return { hourlyData: [], classData: [], totalClassified: 0 };
    }

    // Aggregate class data
    const classCounts = {};
    // Aggregate hourly data (for the last 24h)
    const hours = Array.from({ length: 24 }, (_, i) => ({
      time: `${String(i).padStart(2, '0')}:00`,
      events: 0
    }));

    const now = new Date();

    events.forEach(event => {
      // Classification
      const objClass = event.event_data?.object_class || 'Unidentified';
      classCounts[objClass] = (classCounts[objClass] || 0) + 1;

      // Temporal Density
      const eventDate = new Date(event.start_time);
      if (now - eventDate < 24 * 60 * 60 * 1000) {
        const hour = eventDate.getHours();
        hours[hour].events += 1;
      }
    });

    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#a855f7', '#06b6d4'];
    const formattedClassData = Object.entries(classCounts).map(([name, value], idx) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1),
      value,
      color: colors[idx % colors.length]
    }));

    return {
      hourlyData: hours,
      classData: formattedClassData.sort((a, b) => b.value - a.value),
      totalClassified: formattedClassData.reduce((acc, curr) => acc + curr.value, 0)
    };
  }, [events]);

  const StatCard = ({ title, value, subvalue, icon: Icon, trend, loading }) => (
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
        <h3 className="text-2xl font-black text-white">
          {loading ? <span className="animate-pulse text-white/30">...</span> : value}
        </h3>
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
          Aggregated Analytics & Performance Telemetry &bull; Real-time Data
        </p>
      </header>

      {/* ── Top Row Stats ── */}
      <div className="grid grid-cols-4 gap-6 mb-8">
        <StatCard 
          title="Total Events" 
          value={analytics?.total_events || 0} 
          subvalue="Database" 
          icon={Target} 
          loading={analyticsLoading} 
        />
        <StatCard 
          title="Active Nodes" 
          value={analytics?.online_cameras || 0} 
          subvalue={`/ ${analytics?.total_cameras || 0} Total`} 
          icon={Zap} 
          loading={analyticsLoading} 
        />
        <StatCard 
          title="New Events" 
          value={analytics?.new_events || 0} 
          subvalue="Unresolved" 
          icon={Users} 
          loading={analyticsLoading} 
        />
        <StatCard 
          title="System Uptime" 
          value={`${analytics?.uptime_percentage || 99.9}%`} 
          subvalue="Network" 
          icon={Shield} 
          loading={analyticsLoading} 
        />
      </div>

      <div className="grid grid-cols-12 gap-8">
        {/* ── Main Chart: Temporal Density ── */}
        <div className="col-span-8 bg-neutral-900/30 border border-white/5 rounded-[40px] p-8">
          <div className="flex justify-between items-center mb-8">
            <div>
              <h3 className="text-lg font-black text-white uppercase tracking-tight">Temporal Event Density</h3>
              <p className="text-[10px] font-bold text-neutral-500 uppercase tracking-widest">Event distribution across 24-hour cycle</p>
            </div>
            <div className="flex space-x-2">
              <button className="px-4 py-2 bg-blue-600 text-white rounded-xl text-[10px] font-black uppercase tracking-widest shadow-lg shadow-blue-500/20">24H</button>
            </div>
          </div>
          
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={hourlyData}>
                <defs>
                  <linearGradient id="colorEvt" x1="0" y1="0" x2="0" y2="1">
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
                  interval={3}
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
                  labelStyle={{ color: '#666', fontSize: '10px', fontWeight: 'bold' }}
                />
                <Area type="monotone" dataKey="events" stroke="#3b82f6" strokeWidth={4} fillOpacity={1} fill="url(#colorEvt)" name="Events" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* ── Classification Distribution ── */}
        <div className="col-span-4 bg-neutral-900/30 border border-white/5 rounded-[40px] p-8">
          <h3 className="text-lg font-black text-white uppercase tracking-tight mb-2">Neural Classification</h3>
          <p className="text-[10px] font-bold text-neutral-500 uppercase tracking-widest mb-8">Object distribution by class</p>
          
          <div className="h-64 w-full relative">
            {classData.length > 0 ? (
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
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#121214', border: '1px solid #ffffff10', borderRadius: '12px' }}
                    itemStyle={{ fontSize: '12px', fontWeight: 'bold', color: '#fff' }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-neutral-600 text-xs font-bold uppercase tracking-widest">
                No classification data
              </div>
            )}
            {classData.length > 0 && (
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-2xl font-black text-white">{totalClassified}</span>
                <span className="text-[8px] font-black text-neutral-500 uppercase">Total Items</span>
              </div>
            )}
          </div>

          <div className="mt-6 space-y-3 overflow-y-auto max-h-32 custom-scrollbar pr-2">
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
      </div>
    </div>
  );
};

export default Analytics;
