import React, { useState, useRef, useEffect } from 'react';
import { Bell, X, ShieldAlert, Package, Eye, ChevronDown, Trash2, CheckCheck } from 'lucide-react';
import { useAlertStore } from '../stores/alertStore';

const API_BASE = `${window.location.protocol}//${window.location.hostname}:8000`;

const EVENT_META = {
  intrusion: {
    label: 'Intrusion Détectée',
    icon: ShieldAlert,
    color: '#ef4444',
    bg: 'rgba(239,68,68,0.12)',
    border: 'rgba(239,68,68,0.35)',
  },
  abandoned_object: {
    label: 'Objet Abandonné',
    icon: Package,
    color: '#f59e0b',
    bg: 'rgba(245,158,11,0.12)',
    border: 'rgba(245,158,11,0.35)',
  },
  loitering: {
    label: 'Rôdeur Détecté',
    icon: Eye,
    color: '#a855f7',
    bg: 'rgba(168,85,247,0.12)',
    border: 'rgba(168,85,247,0.35)',
  },
  default: {
    label: 'Alerte Sécurité',
    icon: ShieldAlert,
    color: '#3b82f6',
    bg: 'rgba(59,130,246,0.12)',
    border: 'rgba(59,130,246,0.35)',
  },
};

function formatTime(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function formatEventType(type) {
  return (EVENT_META[type] || EVENT_META.default).label;
}

const AlertCard = ({ alert, onAck }) => {
  const [expanded, setExpanded] = useState(false);
  const meta = EVENT_META[alert.event_type] || EVENT_META.default;
  const Icon = meta.icon;
  const snapshotUrl = alert.snapshot ? `${API_BASE}${alert.snapshot}` : null;

  return (
    <div
      className={`relative rounded-xl mb-2 overflow-hidden transition-all duration-300 cursor-pointer`}
      style={{
        background: alert.acknowledged ? 'rgba(255,255,255,0.03)' : meta.bg,
        border: `1px solid ${alert.acknowledged ? 'rgba(255,255,255,0.08)' : meta.border}`,
        boxShadow: alert.acknowledged ? 'none' : `0 0 18px ${meta.color}22`,
      }}
      onClick={() => setExpanded((v) => !v)}
    >
      {/* Unread bar */}
      {!alert.acknowledged && (
        <div
          className="absolute left-0 top-0 bottom-0 w-0.5 rounded-l-xl"
          style={{ background: meta.color }}
        />
      )}

      {/* Header row */}
      <div className="flex items-center gap-2 px-3 py-2.5 pl-4">
        <div
          className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center"
          style={{ background: `${meta.color}22`, border: `1px solid ${meta.color}44` }}
        >
          <Icon style={{ color: meta.color }} className="w-3.5 h-3.5" />
        </div>
        <div className="flex-1 min-w-0">
          <p
            className="text-[11px] font-black uppercase tracking-widest truncate"
            style={{ color: alert.acknowledged ? '#9ca3af' : '#f1f5f9' }}
          >
            {formatEventType(alert.event_type)}
          </p>
          <p className="text-[9px] text-gray-500 font-mono mt-0.5">
            CAM {alert.camera_id?.substring(0, 8).toUpperCase()} · {formatTime(alert.timestamp)}
          </p>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          {!alert.acknowledged && (
            <button
              onClick={(e) => { e.stopPropagation(); onAck(alert.id); }}
              className="p-1 rounded hover:bg-white/10 transition-colors"
              title="Marquer comme lu"
            >
              <CheckCheck className="w-3 h-3 text-gray-400 hover:text-green-400" />
            </button>
          )}
          <ChevronDown
            className={`w-3 h-3 text-gray-500 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
          />
        </div>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="px-4 pb-3 pt-0 space-y-2.5">
          {/* Snapshot */}
          {snapshotUrl && (
            <div className="rounded-lg overflow-hidden border border-white/10">
              <img
                src={snapshotUrl}
                alt="Capture événement"
                className="w-full object-cover"
                style={{ maxHeight: 140 }}
                onError={(e) => { e.target.parentElement.style.display = 'none'; }}
              />
              <div className="px-2 py-1 text-[8px] font-mono text-gray-500 bg-black/40">
                CAPTURE · {formatTime(alert.timestamp)}
              </div>
            </div>
          )}

          {/* Details grid */}
          <div className="grid grid-cols-2 gap-1.5 text-[9px]">
            {alert.event_data?.object_class && (
              <div className="bg-white/5 rounded px-2 py-1.5">
                <p className="text-gray-500 uppercase tracking-widest mb-0.5">Classe</p>
                <p className="text-white font-bold capitalize">{alert.event_data.object_class}</p>
              </div>
            )}
            {alert.event_data?.zone_name && (
              <div className="bg-white/5 rounded px-2 py-1.5">
                <p className="text-gray-500 uppercase tracking-widest mb-0.5">Zone</p>
                <p style={{ color: meta.color }} className="font-bold truncate">{alert.event_data.zone_name}</p>
              </div>
            )}
            {alert.event_data?.confidence && (
              <div className="bg-white/5 rounded px-2 py-1.5">
                <p className="text-gray-500 uppercase tracking-widest mb-0.5">Confiance</p>
                <p className="text-white font-bold">{Math.round(alert.event_data.confidence * 100)}%</p>
              </div>
            )}
            {alert.severity && (
              <div className="bg-white/5 rounded px-2 py-1.5">
                <p className="text-gray-500 uppercase tracking-widest mb-0.5">Sévérité</p>
                <p
                  className="font-black uppercase"
                  style={{ color: alert.severity === 'high' || alert.severity === 'critical' ? '#ef4444' : meta.color }}
                >
                  {alert.severity}
                </p>
              </div>
            )}
            {alert.event_data?.duration_seconds != null && (
              <div className="bg-white/5 rounded px-2 py-1.5 col-span-2">
                <p className="text-gray-500 uppercase tracking-widest mb-0.5">Durée de présence</p>
                <p className="text-white font-bold">{Math.round(alert.event_data.duration_seconds)}s</p>
              </div>
            )}
          </div>

          {!alert.acknowledged && (
            <button
              onClick={(e) => { e.stopPropagation(); onAck(alert.id); }}
              className="w-full py-1.5 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all"
              style={{
                background: `${meta.color}22`,
                border: `1px solid ${meta.color}44`,
                color: meta.color,
              }}
            >
              Acquitter l'alerte
            </button>
          )}
        </div>
      )}
    </div>
  );
};

const AlertPanel = () => {
  const [open, setOpen] = useState(false);
  const { alerts, acknowledgeAlert, clearAll } = useAlertStore();
  const panelRef = useRef(null);

  const unread = alerts.filter((a) => !a.acknowledged).length;

  // Close on outside click
  useEffect(() => {
    const handler = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div className="relative" ref={panelRef}>
      {/* Bell button */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative p-2 rounded-xl transition-all duration-200 group"
        style={{
          background: open ? 'rgba(239,68,68,0.15)' : 'rgba(255,255,255,0.05)',
          border: open ? '1px solid rgba(239,68,68,0.4)' : '1px solid rgba(255,255,255,0.08)',
        }}
        title="Alertes de sécurité"
      >
        <Bell
          className="w-4.5 h-4.5 transition-colors"
          style={{ color: open ? '#ef4444' : unread > 0 ? '#f59e0b' : '#9ca3af', width: 18, height: 18 }}
        />
        {unread > 0 && (
          <span
            className="absolute -top-1 -right-1 min-w-[18px] h-[18px] rounded-full flex items-center justify-center text-[9px] font-black text-white animate-bounce"
            style={{ background: '#ef4444', boxShadow: '0 0 8px rgba(239,68,68,0.7)' }}
          >
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {/* Dropdown panel */}
      {open && (
        <div
          className="absolute right-0 top-full mt-2 z-[9999] flex flex-col rounded-2xl overflow-hidden"
          style={{
            width: 320,
            maxHeight: '80vh',
            background: 'rgba(10, 12, 20, 0.97)',
            backdropFilter: 'blur(24px)',
            border: '1px solid rgba(255,255,255,0.08)',
            boxShadow: '0 24px 60px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,255,255,0.04)',
          }}
        >
          {/* Panel Header */}
          <div
            className="flex items-center justify-between px-4 py-3 flex-shrink-0"
            style={{ borderBottom: '1px solid rgba(255,255,255,0.07)' }}
          >
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-red-400" />
              <span className="text-[11px] font-black uppercase tracking-[0.15em] text-white">
                Alertes Sécurité
              </span>
              {unread > 0 && (
                <span
                  className="px-1.5 py-0.5 rounded-full text-[9px] font-black text-white"
                  style={{ background: 'rgba(239,68,68,0.7)' }}
                >
                  {unread} NEW
                </span>
              )}
            </div>
            <div className="flex items-center gap-1.5">
              {alerts.length > 0 && (
                <button
                  onClick={clearAll}
                  className="p-1 rounded-lg hover:bg-white/10 transition-colors"
                  title="Tout effacer"
                >
                  <Trash2 className="w-3 h-3 text-gray-500 hover:text-red-400" />
                </button>
              )}
              <button
                onClick={() => setOpen(false)}
                className="p-1 rounded-lg hover:bg-white/10 transition-colors"
              >
                <X className="w-3 h-3 text-gray-500" />
              </button>
            </div>
          </div>

          {/* Alert list */}
          <div className="flex-1 overflow-y-auto p-3" style={{ overflowY: 'auto' }}>
            {alerts.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-10 gap-3">
                <div
                  className="w-12 h-12 rounded-full flex items-center justify-center"
                  style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}
                >
                  <Bell className="w-5 h-5 text-gray-600" />
                </div>
                <p className="text-[10px] font-black uppercase tracking-widest text-gray-600">
                  Aucune alerte active
                </p>
              </div>
            ) : (
              alerts.map((alert) => (
                <AlertCard
                  key={alert.id}
                  alert={alert}
                  onAck={acknowledgeAlert}
                />
              ))
            )}
          </div>

          {/* Footer */}
          {alerts.length > 0 && (
            <div
              className="px-4 py-2 flex-shrink-0"
              style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
            >
              <p className="text-[9px] text-gray-600 text-center font-mono">
                {alerts.length} alertes · {unread} non lues
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default AlertPanel;
