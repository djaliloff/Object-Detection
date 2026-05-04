import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { 
  Bell, 
  Search, 
  Filter, 
  Download, 
  Calendar,
  AlertCircle,
  ShieldCheck,
  Zap,
  RefreshCw
} from 'lucide-react';
import { eventsAPI } from '../utils/api';
import EventTimeline from '../components/EventTimeline';
import toast from 'react-hot-toast';

const Events = () => {
  const [filterType, setFilterType] = useState('all');
  const [filterSeverity, setFilterSeverity] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  const { data: events, isLoading, refetch } = useQuery({
    queryKey: ['events'],
    queryFn: () => eventsAPI.getEvents(),
    refetchInterval: 10000,
  });

  const filteredEvents = useMemo(() => {
    if (!Array.isArray(events)) return [];
    return events.filter(event => {
      const matchesType = filterType === 'all' || event.event_type === filterType;
      const matchesSeverity = filterSeverity === 'all' || event.severity === filterSeverity;
      const matchesSearch = !searchQuery || 
        event.event_type.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (event.camera_name && event.camera_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (event.location && event.location.toLowerCase().includes(searchQuery.toLowerCase()));
      return matchesType && matchesSeverity && matchesSearch;
    });
  }, [events, filterType, filterSeverity, searchQuery]);

  const severityStats = useMemo(() => {
    if (!Array.isArray(events)) return { critical: 0, high: 0, total: 0 };
    return {
      critical: events.filter(e => e.severity === 'critical').length,
      high: events.filter(e => e.severity === 'high').length,
      total: events.length
    };
  }, [events]);

  const handleExport = () => {
    toast.success('Exporting tactical logs...', {
      icon: '📥',
      style: { background: '#121214', color: '#fff', border: '1px solid #262626' }
    });
  };

  return (
    <div className="h-screen bg-[#0a0a0c] text-neutral-200 flex flex-col overflow-hidden">
      <div className="p-8 flex-1 flex flex-col min-h-0">
        {/* ── Header ── */}
        <header className="flex justify-between items-end mb-8 shrink-0">
          <div>
            <div className="flex items-center space-x-3 mb-2">
              <div className="p-3 bg-red-600/20 rounded-2xl border border-red-500/30">
                <Bell className="w-6 h-6 text-red-500" />
              </div>
              <h1 className="text-3xl font-black bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent uppercase tracking-tighter">
                Neural Event Log
              </h1>
            </div>
            <p className="text-[10px] font-black uppercase tracking-[0.3em] text-neutral-500">
              Nexus-7 Centralized Telemetry Feed &bull; Real-time Monitoring
            </p>
          </div>

          <div className="flex items-center space-x-6">
            <div className="flex flex-col items-end">
              <span className="text-[10px] font-black text-red-500 uppercase tracking-widest mb-1">Critical Alerts</span>
              <span className="text-3xl font-black text-white">{severityStats.critical}</span>
            </div>
            <div className="w-px h-10 bg-white/10" />
            <div className="flex flex-col items-end">
              <span className="text-[10px] font-black text-orange-500 uppercase tracking-widest mb-1">High Severity</span>
              <span className="text-3xl font-black text-white">{severityStats.high}</span>
            </div>
            <div className="w-px h-10 bg-white/10" />
            <div className="flex flex-col items-end">
              <span className="text-[10px] font-black text-blue-500 uppercase tracking-widest mb-1">Total Logs</span>
              <span className="text-3xl font-black text-white">{severityStats.total}</span>
            </div>
          </div>
        </header>

        {/* ── Tactical Controls ── */}
        <div className="grid grid-cols-12 gap-4 mb-6 shrink-0">
          <div className="col-span-4 relative group">
            <div className="absolute inset-y-0 left-5 flex items-center pointer-events-none">
              <Search className="w-4 h-4 text-neutral-600 group-focus-within:text-blue-500 transition-colors" />
            </div>
            <input 
              type="text" 
              placeholder="SEARCH NEURAL SIGNATURES..." 
              className="w-full bg-neutral-900/50 border border-white/5 rounded-2xl py-4 pl-14 pr-6 outline-none focus:ring-2 ring-blue-500/50 text-xs font-bold text-white transition-all tracking-widest"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <div className="col-span-3 flex items-center bg-neutral-900/50 border border-white/5 rounded-2xl p-1">
            {['all', 'intrusion', 'loitering', 'abandoned_object'].map(type => (
              <button
                key={type}
                onClick={() => setFilterType(type)}
                className={`flex-1 py-3 rounded-xl text-[9px] font-black uppercase tracking-widest transition-all ${
                  filterType === type ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20' : 'text-neutral-500 hover:text-white'
                }`}
              >
                {type.replace('_', ' ')}
              </button>
            ))}
          </div>

          <div className="col-span-3 flex items-center bg-neutral-900/50 border border-white/5 rounded-2xl p-1">
            {['all', 'critical', 'high', 'medium'].map(sev => (
              <button
                key={sev}
                onClick={() => setFilterSeverity(sev)}
                className={`flex-1 py-3 rounded-xl text-[9px] font-black uppercase tracking-widest transition-all ${
                  filterSeverity === sev ? 'bg-red-600 text-white shadow-lg' : 'text-neutral-500 hover:text-white'
                }`}
              >
                {sev}
              </button>
            ))}
          </div>

          <div className="col-span-2 flex space-x-2">
            <button 
              onClick={handleExport}
              className="flex-1 bg-white/5 border border-white/10 rounded-2xl flex items-center justify-center hover:bg-white/10 transition-all active:scale-95"
            >
              <Download className="w-4 h-4 text-white" />
            </button>
            <button 
              onClick={() => refetch()}
              className="flex-1 bg-blue-600/10 border border-blue-500/20 rounded-2xl flex items-center justify-center hover:bg-blue-600/20 transition-all active:scale-95"
            >
              <RefreshCw className={`w-4 h-4 text-blue-400 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* ── Main Content ── */}
        <div className="flex-1 bg-neutral-900/20 rounded-[40px] border border-white/5 flex overflow-hidden">
          {/* Timeline Scroll Area */}
          <div className="flex-1 overflow-y-auto p-10 custom-scrollbar">
            <div className="max-w-4xl mx-auto">
              <div className="flex items-center space-x-4 mb-10">
                <div className="h-px flex-1 bg-gradient-to-r from-transparent via-white/10 to-transparent" />
                <div className="flex items-center space-x-2 text-[10px] font-black text-neutral-500 uppercase tracking-[0.4em]">
                  <Calendar className="w-3.5 h-3.5" />
                  <span>Tactical Archive: {new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}</span>
                </div>
                <div className="h-px flex-1 bg-gradient-to-r from-transparent via-white/10 to-transparent" />
              </div>

              {isLoading ? (
                <div className="flex flex-col items-center justify-center py-40 space-y-4">
                  <div className="w-10 h-10 border-2 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
                  <p className="text-[10px] font-black text-neutral-600 uppercase tracking-widest">Synchronizing Logs...</p>
                </div>
              ) : (
                <EventTimeline events={filteredEvents} />
              )}
            </div>
          </div>

          {/* Right Panel: Active Status */}
          <div className="w-80 border-l border-white/5 p-8 flex flex-col space-y-8 bg-black/20">
             <div>
                <h3 className="text-[10px] font-black text-white/40 uppercase tracking-[0.3em] mb-6">Neural Status</h3>
                <div className="space-y-4">
                   <div className="p-5 bg-white/5 rounded-3xl border border-white/5 hover:border-blue-500/30 transition-all">
                      <div className="flex items-center space-x-3 mb-3">
                         <Zap className="w-4 h-4 text-yellow-400" />
                         <span className="text-xs font-bold text-white uppercase tracking-tight">AI Processor</span>
                      </div>
                      <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden">
                         <div className="bg-blue-500 h-full w-[85%] animate-pulse" />
                      </div>
                      <p className="text-[9px] font-black text-neutral-500 mt-2 uppercase tracking-widest">Load: 85% | 14.2 GFLOPs</p>
                   </div>

                   <div className="p-5 bg-white/5 rounded-3xl border border-white/5 hover:border-green-500/30 transition-all">
                      <div className="flex items-center space-x-3 mb-3">
                         <ShieldCheck className="w-4 h-4 text-green-400" />
                         <span className="text-xs font-bold text-white uppercase tracking-tight">Active Sentinel</span>
                      </div>
                      <p className="text-[9px] font-black text-green-500 uppercase tracking-widest leading-relaxed">
                         Global Defense Grid: ACTIVE<br />
                         All 4 Sectors Monitored
                      </p>
                   </div>
                </div>
             </div>

             <div className="flex-1 bg-gradient-to-b from-blue-600/10 to-transparent rounded-[32px] border border-blue-500/10 p-6 flex flex-col items-center justify-center text-center">
                <AlertCircle className="w-10 h-10 text-blue-400 mb-4 animate-bounce" />
                <h4 className="text-sm font-black text-white uppercase tracking-tight mb-2">Automated Response</h4>
                <p className="text-[10px] text-neutral-500 font-medium leading-relaxed mb-6">
                   Security protocols are automatically engaged based on neural trigger severity.
                </p>
                <button className="w-full py-3 bg-blue-600 text-white text-[10px] font-black uppercase tracking-widest rounded-xl shadow-xl shadow-blue-600/20 hover:bg-blue-500 transition-all">
                   View Protocols
                </button>
             </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Events;
