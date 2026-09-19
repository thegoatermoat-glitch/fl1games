import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { X, Maximize, RotateCw, Smartphone, Clock, Users, AlertTriangle } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function clientId() {
  let id = localStorage.getItem('fl1nt_client_id');
  if (!id) { id = (crypto.randomUUID ? crypto.randomUUID() : String(Math.random()).slice(2)); localStorage.setItem('fl1nt_client_id', id); }
  return id;
}
function fmt(sec) {
  sec = Math.max(0, Math.floor(sec));
  const m = String(Math.floor(sec / 60)).padStart(2, '0');
  const s = String(sec % 60).padStart(2, '0');
  return `${m}:${s}`;
}

export default function CloudPhonePlayer({ game, onClose }) {
  const [phase, setPhase] = useState('joining'); // joining|queued|active|ended|error
  const [queue, setQueue] = useState({ position: 0, activeCount: 0, maxSlots: 20 });
  const [remaining, setRemaining] = useState(30 * 60);
  const [streamUrl, setStreamUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  const cid = useRef(clientId());
  const frameRef = useRef(null);
  const pollRef = useRef(null);
  const tickRef = useRef(null);
  const phaseRef = useRef('joining');
  const leftRef = useRef(false);

  const setPhaseBoth = (p) => { phaseRef.current = p; setPhase(p); };

  const leave = useCallback((useBeacon) => {
    if (leftRef.current) return;
    leftRef.current = true;
    if (frameRef.current) { try { frameRef.current.src = 'about:blank'; } catch (e) { /* ignore */ } }
    if (pollRef.current) clearInterval(pollRef.current);
    if (tickRef.current) clearInterval(tickRef.current);
    const url = `${API}/cloudphone/session/leave`;
    const payload = JSON.stringify({ clientId: cid.current });
    if (useBeacon && navigator.sendBeacon) navigator.sendBeacon(url, new Blob([payload], { type: 'application/json' }));
    else axios.post(url, { clientId: cid.current }).catch(() => {});
  }, []);

  const applyStatus = useCallback((data) => {
    if (leftRef.current) return;
    if (data.status === 'queued') {
      setPhaseBoth('queued');
      setQueue({ position: data.position, activeCount: data.activeCount, maxSlots: data.maxSlots });
    } else if (data.status === 'active') {
      if (typeof data.remainingSeconds === 'number') setRemaining(data.remainingSeconds);
      if (data.streamUrl) { setStreamUrl(data.streamUrl); setLoading(true); }
      if (phaseRef.current !== 'active') setPhaseBoth('active');
    } else if (data.status === 'none') {
      // dropped by server (e.g. missed heartbeats) -> rejoin
      axios.post(`${API}/cloudphone/session/join`, { clientId: cid.current }).then(({ data: d }) => applyStatus(d)).catch(() => {});
    }
  }, []);

  // join on open
  useEffect(() => {
    leftRef.current = false;
    setPhaseBoth('joining'); setError(null);
    axios.post(`${API}/cloudphone/session/join`, { clientId: cid.current })
      .then(({ data }) => applyStatus(data))
      .catch((err) => { setError(err.response?.data?.detail || 'Could not join the cl0ud phone.'); setPhaseBoth('error'); });
    return () => leave(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadKey]);

  // heartbeat poll every 8s
  useEffect(() => {
    pollRef.current = setInterval(() => {
      if (leftRef.current || phaseRef.current === 'ended' || phaseRef.current === 'error') return;
      axios.post(`${API}/cloudphone/session/heartbeat`, { clientId: cid.current })
        .then(({ data }) => applyStatus(data)).catch(() => {});
    }, 8000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [applyStatus]);

  // local countdown while active
  useEffect(() => {
    tickRef.current = setInterval(() => {
      if (phaseRef.current !== 'active') return;
      setRemaining((r) => {
        if (r <= 1) { setPhaseBoth('ended'); leave(false); return 0; }
        return r - 1;
      });
    }, 1000);
    return () => { if (tickRef.current) clearInterval(tickRef.current); };
  }, [leave]);

  // stop on tab close + escape + lock scroll
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') { leave(false); onClose(); } };
    const onUnload = () => leave(true);
    window.addEventListener('keydown', onKey);
    window.addEventListener('beforeunload', onUnload);
    window.addEventListener('pagehide', onUnload);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('beforeunload', onUnload);
      window.removeEventListener('pagehide', onUnload);
      document.body.style.overflow = '';
    };
  }, [leave, onClose]);

  const goFullscreen = () => { const el = frameRef.current; if (el && el.requestFullscreen) el.requestFullscreen(); };
  const handleClose = () => { leave(false); onClose(); };
  const restart = () => { leftRef.current = false; setStreamUrl(null); setError(null); setLoading(true); setRemaining(30 * 60); setReloadKey((k) => k + 1); };

  const lowTime = remaining <= 120 && remaining > 0;

  return (
    <div className="player-overlay">
      <div className="player-bar">
        <div className="player-title">
          <Smartphone size={18} style={{ color: game.colorA }} />
          {game.name}
        </div>
        <div className="player-actions">
          {phase === 'active' && (
            <span className={`session-timer ${lowTime ? 'low' : ''}`} title="Time left in this 30-min session">
              <Clock size={14} /> {fmt(remaining)} left
            </span>
          )}
          <button onClick={restart} title="Reconnect"><RotateCw size={16} /> Reconnect</button>
          <button onClick={goFullscreen} title="Fullscreen"><Maximize size={16} /> Fullscreen</button>
          <button className="close" onClick={handleClose} title="Close"><X size={16} /> Close</button>
        </div>
      </div>

      <div className="player-stage">
        {phase === 'error' ? (
          <div className="player-loading">
            <AlertTriangle size={40} style={{ color: 'var(--accent)' }} />
            <p>Cl0ud phone unavailable</p>
            <span className="player-loading-hint">{error}</span>
          </div>
        ) : phase === 'ended' ? (
          <div className="player-loading">
            <AlertTriangle size={40} style={{ color: 'var(--accent)' }} />
            <p>Your 30-minute session ended</p>
            <span className="player-loading-hint">Hit Reconnect to grab another slot (you may re-enter the queue).</span>
          </div>
        ) : phase === 'queued' ? (
          <div className="player-loading">
            <Users size={40} style={{ color: 'var(--accent)' }} />
            <p>You're in the queue</p>
            <span className="player-loading-hint">
              Position <b style={{ color: 'var(--accent)' }}>#{queue.position}</b> &middot; {queue.activeCount}/{queue.maxSlots} phones in use.
              We'll drop you in automatically when a slot frees up.
            </span>
          </div>
        ) : (
          <>
            {(phase === 'joining' || loading || !streamUrl) && (
              <div className="player-loading">
                <div className="spinner" />
                <p>{phase === 'joining' ? 'Joining...' : 'Booting virtual Android phone...'}</p>
                <span className="player-loading-hint">30-minute session &middot; up to {queue.maxSlots} players at once</span>
              </div>
            )}
            {streamUrl && (
              <iframe
                key={reloadKey}
                ref={frameRef}
                title={game.name}
                src={streamUrl}
                onLoad={() => setLoading(false)}
                allow="autoplay; fullscreen; gamepad; accelerometer; gyroscope; clipboard-write; microphone; camera"
                className={loading ? 'loading' : ''}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}
