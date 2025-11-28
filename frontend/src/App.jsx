import { useCallback, useEffect, useMemo, useState } from 'react';
import ControlPanel from './components/ControlPanel.jsx';
import DetectionLog from './components/DetectionLog.jsx';
import LiveFrame from './components/LiveFrame.jsx';

const DEFAULT_BACKEND = 'http://localhost:8000';

function App() {
  const [backendInfo, setBackendInfo] = useState({ host: 'localhost', port: 8000, detector_host: 'localhost', detector_port: 8001 });
  const [discoveryError, setDiscoveryError] = useState(null);
  const [events, setEvents] = useState([]);
  const [lastDetection, setLastDetection] = useState(null);
  const [frameB64, setFrameB64] = useState(null);
  const backendBase = useMemo(() => `http://${backendInfo.host}:${backendInfo.port}`, [backendInfo]);
  const detectorBase = useMemo(() => `http://${backendInfo.detector_host}:${backendInfo.detector_port}`, [backendInfo]);

  useEffect(() => {
    async function discover() {
      try {
        const response = await fetch(`${DEFAULT_BACKEND}/_discover`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const payload = await response.json();
        setBackendInfo(prev => ({
          host: payload.host ?? prev.host,
          port: payload.port ?? prev.port,
          detector_host: payload.detector_host ?? prev.detector_host,
          detector_port: payload.detector_port ?? prev.detector_port,
        }));
        setDiscoveryError(null);
      } catch (error) {
        setDiscoveryError(error.message);
      }
    }
    discover();
  }, []);

  useEffect(() => {
    const eventSource = new EventSource(`${detectorBase}/events`);
    eventSource.onmessage = event => {
      try {
        const payload = JSON.parse(event.data);
        if (payload?.type === 'detection') {
          setLastDetection(payload.payload);
          setEvents(prev => [payload.payload, ...prev].slice(0, 50));
        }
      } catch (error) {
        console.warn('Failed to parse SSE payload', error);
      }
    };
    eventSource.onerror = error => {
      console.warn('SSE connection error', error);
    };
    return () => eventSource.close();
  }, [detectorBase]);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const response = await fetch(`${backendBase}/last_frame`);
        if (!response.ok) return;
        const payload = await response.json();
        if (payload.image_b64) {
          setFrameB64(payload.image_b64);
        }
        if (payload.last_detection) {
          setLastDetection(payload.last_detection);
          setEvents(prev => [payload.last_detection, ...prev].slice(0, 50));
        }
      } catch (error) {
        console.debug('Frame poll failed', error);
      }
    }, 4000);
    return () => clearInterval(interval);
  }, [backendBase]);

  const sendCommand = useCallback(async (path, params) => {
    const url = new URL(`${backendBase}${path}`);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        url.searchParams.set(key, String(value));
      });
    }
    const response = await fetch(url, { method: 'POST' });
    if (!response.ok) {
      throw new Error(`Command failed: ${response.status}`);
    }
    return response.json();
  }, [backendBase]);

  return (
    <div style={{ fontFamily: 'system-ui', padding: '2rem' }}>
      <h1>Train Shunting Prototype</h1>
      {discoveryError && <p style={{ color: 'red' }}>Discovery failed: {discoveryError}</p>}
      <p>Backend: {backendBase} | Detector: {detectorBase}</p>
      <ControlPanel
        onStop={() => sendCommand('/cmd/stop')}
        onForward={() => sendCommand('/cmd/forward', { speed: 110 })}
        onReverse={() => sendCommand('/cmd/reverse', { speed: 80, duration: 1.5 })}
      />
      <LiveFrame imageB64={frameB64} detection={lastDetection} />
      <DetectionLog events={events} />
    </div>
  );
}

export default App;
