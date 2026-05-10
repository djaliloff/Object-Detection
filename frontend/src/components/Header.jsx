import React, { useState, useEffect } from 'react';
import { Search } from 'lucide-react';
import AlertPanel from './AlertPanel';

const Header = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [currentTime, setCurrentTime] = useState(new Date().toLocaleTimeString());

  useEffect(() => {
    const t = setInterval(() => setCurrentTime(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <header
      className="px-6 py-3 flex-shrink-0"
      style={{
        background: 'rgba(10,12,20,0.92)',
        backdropFilter: 'blur(20px)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      <div className="flex items-center justify-between gap-4">
        {/* Search */}
        <div className="flex-1 max-w-md">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              type="text"
              placeholder="Rechercher caméras, événements..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-sm text-white placeholder-gray-600 rounded-xl focus:outline-none transition-all"
              style={{
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.08)',
              }}
            />
          </div>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-3">
          {/* Real-time clock */}
          <div
            className="px-3 py-1.5 rounded-xl"
            style={{
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.07)',
            }}
          >
            <span className="text-[10px] font-mono font-bold text-gray-400 tracking-widest">
              {currentTime}
            </span>
          </div>

          {/* System status */}
          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-xl"
            style={{
              background: 'rgba(34,197,94,0.08)',
              border: '1px solid rgba(34,197,94,0.2)',
            }}
          >
            <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            <span className="text-[10px] font-black uppercase tracking-widest text-green-400">
              System Online
            </span>
          </div>

          {/* Alert Notification Bell */}
          <AlertPanel />
        </div>
      </div>
    </header>
  );
};

export default Header;
