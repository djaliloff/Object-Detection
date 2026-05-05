import { useEffect, useRef } from 'react';
import { useAlertStore } from '../stores/alertStore';
import { eventsAPI } from '../utils/api';

const POLL_INTERVAL_MS = 4000; // poll every 4 seconds

/**
 * GlobalAlertListener — headless component mounted once at Layout level.
 * Polls /api/v1/events for new (status="new") events and feeds the alertStore.
 * Uses a seenIds set to avoid duplicate notifications.
 */
const GlobalAlertListener = () => {
  const { addAlert, alerts } = useAlertStore();
  const seenIds = useRef(new Set(alerts.map((a) => a.id)));
  const timerRef = useRef(null);
  const mountedRef = useRef(true);

  const poll = async () => {
    if (!mountedRef.current) return;
    try {
      const events = await eventsAPI.getEvents({ limit: 30, offset: 0 });
      if (!mountedRef.current) return;

      const newEvents = (events || []).filter(
        (ev) => ev.status === 'new' && !seenIds.current.has(ev.id)
      );

      for (const ev of newEvents) {
        seenIds.current.add(ev.id);
        addAlert({
          id: ev.id,
          event_type: ev.event_type,
          camera_id: ev.camera_id,
          event_data: ev.event_data || {},
          severity: ev.severity,
          zone_id: ev.zone_id,
          snapshot_refs: ev.snapshot_refs,
          start_time: ev.start_time || ev.created_at,
        });
      }
    } catch (e) {
      // silently ignore network errors
    }

    if (mountedRef.current) {
      timerRef.current = setTimeout(poll, POLL_INTERVAL_MS);
    }
  };

  useEffect(() => {
    mountedRef.current = true;
    // Start polling immediately
    poll();
    return () => {
      mountedRef.current = false;
      clearTimeout(timerRef.current);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
};

export default GlobalAlertListener;
