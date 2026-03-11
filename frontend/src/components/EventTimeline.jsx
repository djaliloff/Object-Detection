import React from 'react';
import { 
  AlertTriangle, 
  Shield, 
  Clock, 
  User, 
  Car, 
  Box, 
  Activity,
  ChevronRight
} from 'lucide-react';

const EventTimeline = ({ events = [] }) => {
  const getEventIcon = (eventType) => {
    switch (eventType) {
      case 'intrusion': return <Shield className="w-4 h-4" />;
      case 'person': return <User className="w-4 h-4" />;
      case 'vehicle': return <Car className="w-4 h-4" />;
      case 'abandoned_object': return <Box className="w-4 h-4" />;
      default: return <Activity className="w-4 h-4" />;
    }
  };

  const getSeverityStyle = (severity) => {
    const styles = {
      critical: 'from-red-600/20 to-red-600/5 border-red-500/30 text-red-400',
      high: 'from-orange-600/20 to-orange-600/5 border-orange-500/30 text-orange-400',
      medium: 'from-blue-600/20 to-blue-600/5 border-blue-500/30 text-blue-400',
      low: 'from-green-600/20 to-green-600/5 border-green-500/30 text-green-400',
    };
    return styles[severity] || styles.medium;
  };

  return (
    <div className="relative">
      {events.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 bg-white/5 rounded-[32px] border border-white/5 border-dashed">
          <Activity className="w-12 h-12 text-neutral-800 mb-4" />
          <p className="text-[10px] font-black uppercase tracking-widest text-neutral-600">No telemetry detected</p>
        </div>
      ) : (
        <div className="space-y-6">
          {events.map((event, index) => (
            <div 
              key={event.id} 
              className="group relative flex items-start space-x-4 animate-in fade-in slide-in-from-right duration-500"
              style={{ animationDelay: `${index * 100}ms` }}
            >
              <div className="flex flex-col items-center">
                <div className={`p-2.5 rounded-xl bg-neutral-900 border border-white/10 group-hover:scale-110 transition-transform ${event.severity === 'critical' ? 'text-red-500' : 'text-neutral-400'}`}>
                  {getEventIcon(event.event_type)}
                </div>
                {index !== events.length - 1 && (
                  <div className="w-px h-full bg-gradient-to-b from-white/10 to-transparent my-2" />
                )}
              </div>

              <div className={`flex-1 p-6 bg-gradient-to-br rounded-[24px] border ${getSeverityStyle(event.severity)} transition-all hover:translate-x-1`}>
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="text-[10px] font-black uppercase tracking-widest mb-1 opacity-60">
                       Neural Trigger: {event.event_type.replace('_', ' ')}
                    </h3>
                    <div className="flex items-center space-x-2">
                       <p className="text-white font-bold text-sm tracking-tight">{event.camera_name || `NEXUS_${event.camera_id}`}</p>
                       <ChevronRight className="w-3 h-3 text-neutral-500" />
                       <p className="text-white/60 text-[10px] font-black uppercase tracking-widest">Sector {event.location || '7-G'}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="flex items-center space-x-1 mb-1">
                       <Clock className="w-3 h-3 opacity-40" />
                       <span className="text-[10px] font-black text-white/50">{new Date(event.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
                    </div>
                    <span className="text-[8px] font-black uppercase tracking-tighter px-2 py-0.5 bg-white/10 rounded-full border border-white/10">
                      {event.severity}
                    </span>
                  </div>
                </div>

                <div className="flex items-center space-x-4">
                   <div className="p-3 bg-white/5 rounded-2xl border border-white/5 flex-1 group-hover:border-white/20 transition-colors">
                      <p className="text-[8px] font-black text-neutral-500 uppercase mb-1">Detection Logic</p>
                      <p className="text-[10px] text-white font-bold leading-tight uppercase">
                         {event.event_data?.object_class || 'Unknown'} - Confidence {((event.event_data?.confidence || 0.85) * 100).toFixed(0)}%
                      </p>
                   </div>
                   <button className="p-3 bg-white/5 rounded-2xl border border-white/5 hover:bg-white/10 transition-colors">
                      <AlertTriangle className="w-4 h-4" />
                   </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default EventTimeline;
