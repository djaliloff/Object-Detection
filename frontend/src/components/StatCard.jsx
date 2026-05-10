import React from 'react';

const StatCard = ({ title, value, icon, color, subtitle, trend, loading }) => {
  const getColorClasses = (color) => {
    const colors = {
      blue: 'bg-blue-600/20 text-blue-400 border-blue-500/30',
      green: 'bg-green-600/20 text-green-400 border-green-500/30',
      red: 'bg-red-600/20 text-red-400 border-red-500/30',
      yellow: 'bg-yellow-600/20 text-yellow-400 border-yellow-500/30',
      purple: 'bg-purple-600/20 text-purple-400 border-purple-500/30',
      orange: 'bg-orange-600/20 text-orange-400 border-orange-500/30',
    };
    return colors[color] || colors.blue;
  };

  return (
    <div className="relative group bg-neutral-900/40 backdrop-blur-3xl border border-white/5 rounded-[32px] p-6 transition-all hover:bg-neutral-800/60 hover:-translate-y-1">
      <div className="absolute top-0 right-0 p-6 opacity-0 group-hover:opacity-100 transition-opacity">
         <div className="w-12 h-12 bg-white/5 rounded-full blur-2xl" />
      </div>

      <div className="flex items-center justify-between mb-4">
        <div className={`p-3 rounded-2xl border ${getColorClasses(color)}`}>
          {icon}
        </div>
        {trend && (
           <span className={`text-[10px] font-black uppercase tracking-widest px-2 py-1 rounded-lg ${trend > 0 ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
              {trend > 0 ? '+' : ''}{trend}%
           </span>
        )}
      </div>

      <div className="space-y-1">
        <p className="text-[10px] font-black uppercase tracking-widest text-neutral-500">{title}</p>
        <div className="flex items-baseline space-x-2">
          {loading ? (
            <div className="h-9 w-24 bg-white/5 rounded-xl animate-pulse" />
          ) : (
            <p className="text-3xl font-black text-white tracking-tighter">{value}</p>
          )}
          {subtitle && (
            <p className="text-[10px] font-bold text-neutral-600 uppercase tracking-widest">{subtitle}</p>
          )}
        </div>
      </div>
      
      {/* Dynamic line effect */}
      <div className="absolute bottom-0 left-8 right-8 h-px bg-gradient-to-r from-transparent via-blue-500/20 to-transparent scale-x-0 group-hover:scale-x-100 transition-transform duration-500" />
    </div>
  );
};

export default StatCard;
