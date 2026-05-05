import { create } from 'zustand';

const useAlertStore = create((set, get) => ({
  alerts: [], // { id, event_type, camera_id, event_data, snapshot, timestamp, acknowledged }

  addAlert: (alertData) => {
    const id = alertData.id || `alert-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const newAlert = {
      id,
      event_type: alertData.event_type,
      camera_id: alertData.camera_id,
      event_data: alertData.event_data || {},
      snapshot: alertData.snapshot_refs?.frame || null,
      severity: alertData.severity || 'medium',
      zone_id: alertData.zone_id,
      timestamp: alertData.start_time ? new Date(alertData.start_time).getTime() : Date.now(),
      acknowledged: false,
    };
    set((state) => ({
      alerts: [newAlert, ...state.alerts].slice(0, 50), // keep last 50
    }));
  },

  acknowledgeAlert: (id) => {
    set((state) => ({
      alerts: state.alerts.map((a) => (a.id === id ? { ...a, acknowledged: true } : a)),
    }));
  },

  clearAll: () => set({ alerts: [] }),

  unacknowledgedCount: () => get().alerts.filter((a) => !a.acknowledged).length,
}));

export { useAlertStore };
