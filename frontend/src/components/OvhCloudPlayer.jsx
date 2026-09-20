import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { X, Maximize, RotateCw, Keyboard, Loader2, Users, Settings } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const SESSION_SECONDS = 25 * 60;

function getClientId() {
  let id = localStorage.getItem('fl1nt_ovh_cid');
  if (!id) { id = (crypto.randomUUID ? crypto.randomUUID() : String(Math.random()).slice(2)); localStorage.setItem('fl1nt_ovh_cid', id); }
  return id;
}

export default function OvhCloudPlayer({ game, onClose }) {
  const [phase, setPhase] = useState('connecting');   // connecting | queued | active | error
  const [position, setPosition] = useState(0);
  const [remaining, setRemaining] = useState(SESSION_SECONDS);
  const [streamUrl, setStreamUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [needFocus, setNeedFocus] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);
  const [error, setError] = useState(null);
  const [configuring, setConfiguring] = useState(false);
  const [orchUrl, setOrchUrl] = useState('');
  const [orchToken, setOrchToken] = useState('');

  const cid = useRef(getClientId());
  const leftRef = useRef(false);
  const frameRef = useRef(null);
  const stageRef = useRef(null);

  const applyStatus = useCallback((data) => {
    if (leftRef.current) return;
    if (data.error) setError(data.error); else setError(null);
    if (data.status === 'queued') {
      setPhase('queued'); setPosition(data.position || 1);
    } else if (data.status === 'active') {
      setPhase('active');
      if (typeof data.remainingSeconds === 'number') setRemaining(data.remainingSeconds);
      if (data.streamUrl) setStreamUrl(data.streamUrl);
    } else if (data.status === 'none') {
      axios.post(`${API}/ovh/session/join`, { clientId: cid.current }).then(({ data: d }) => applyStatus(d)).catch(() => {});
    }
  }, []);

  useEffect(() => {
    leftRef.current = false;
    axios.post(`${API}/ovh/session/join`, { clientId: cid.current }).then(({ data }) => applyStatus(data)).catch(() => setError('Could not reach the server.'));
    const hb = setInterval(() => {
      axios.post(`${API}/ovh/session/heartbeat`, { clientId: cid.current }).then(({ data }) => applyStatus(data)).catch(() => {});
    }, 8000);
    const leave = () => {
      leftRef.current = true;
      try {
        const blob = new Blob([JSON.stringify({ clientId: cid.current })], { type: 'application/json' });
        navigator.sendBeacon(`${API}/ovh/session/leave`, blob);
      } catch (e) { /* noop */ }
    };
    window.addEventListener('beforeunload', leave);
    const onKey = (e) => { if (e.key === 'Escape' && !document.fullscreenElement) onClose(); };
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      clearInterval(hb);
      window.removeEventListener('beforeunload', leave);
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
      leave();
    };
  }, [applyStatus, onClose, reloadKey]);

  // local countdown
  useEffect(() => {
    if (phase !== 'active') return;
    const t = setInterval(() => setRemaining((r) => Math.max(0, r - 1)), 1000);
    return () => clearInterval(t);
  }, [phase]);

  const mmss = `${String(Math.floor(remaining / 60)).padStart(2, '0')}:${String(remaining % 60).padStart(2, '0')}`;
  const lowTime = remaining <= 120;

  const focusScreen = () => { if (frameRef.current) { frameRef.current.focus(); setNeedFocus(false); } };
  const goFullscreen = () => {
    const el = stageRef.current;
    if (el && el.requestFullscreen) el.requestFullscreen().then(() => setTimeout(focusScreen, 300));
  };
  const reconnect = () => { setLoading(true); setStreamUrl(null); setReloadKey((k) => k + 1); };

  const saveConfig = () => {
    axios.post(`${API}/ovh/config`, { url: orchUrl.trim(), token: orchToken.trim() })
      .then(() => { setConfiguring(false); reconnect(); }).catch(() => {});
  };

  return (
    <div className="player-overlay" data-testid="ovh-player">
      <div className="player-bar">
        <div className="player-title">
          <span className="player-dot" style={{ background: game.colorA }} />
          {game.name} <span style={{ opacity: 0.5, fontWeight: 400, marginLeft: 6 }}>· self-host cl0ud</span>
          {phase === 'active' && (
            <span data-testid="ovh-timer" style={{ marginLeft: 12, fontSize: 13, color: lowTime ? '#ff8a8a' : 'rgba(255,255,255,0.65)' }}>{mmss} left</span>
          )}
        </div>
        <div className="player-actions">
          <button onClick={() => setConfiguring((v) => !v)} title="Orchestrator settings" data-testid="ovh-config-btn">
            <Settings size={16} /> Server
          </button>
          {phase === 'active' && (
            <button onClick={reconnect} title="Reconnect" data-testid="ovh-reload-btn"><RotateCw size={16} /> Reconnect</button>
          )}
          {phase === 'active' && (
            <button onClick={goFullscreen} title="Fullscreen" data-testid="ovh-fullscreen-btn"><Maximize size={16} /> Fullscreen</button>
          )}
          <button className="close" onClick={onClose} title="Close" data-testid="ovh-close-btn"><X size={16} /> Close</button>
        </div>
      </div>

      <div className="player-stage" ref={stageRef} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {configuring && (
          <div className="player-loading" data-testid="ovh-config-panel" style={{ maxWidth: 560 }}>
            <Settings size={36} style={{ color: game.colorA }} />
            <p>Connect your VPS orchestrator</p>
            <span className="player-loading-hint">Paste the public base URL of the orchestrator running on your OVH VPS (and its token if set). It allocates one redroid phone per user.</span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 14, width: '100%' }}>
              <input data-testid="ovh-orch-url" value={orchUrl} onChange={(e) => setOrchUrl(e.target.value)} placeholder="https://your-vps-domain:9000" style={inputStyle} />
              <input data-testid="ovh-orch-token" value={orchToken} onChange={(e) => setOrchToken(e.target.value)} placeholder="orchestrator token (optional)" style={inputStyle} />
              <button onClick={saveConfig} data-testid="ovh-orch-save" style={{ padding: '10px 18px', borderRadius: 10, border: 'none', background: game.colorA, color: '#111', fontWeight: 700, cursor: 'pointer' }}>Save & connect</button>
            </div>
          </div>
        )}

        {!configuring && phase === 'connecting' && (
          <div className="player-loading"><div className="spinner" /><p>Reserving a cl0ud phone...</p></div>
        )}

        {!configuring && phase === 'queued' && (
          <div className="player-loading" data-testid="ovh-queue">
            <Users size={38} style={{ color: game.colorA }} />
            <p>All phones are busy right now</p>
            <span className="player-loading-hint">You're <b>#{position}</b> in the queue. Keep this open — your phone starts automatically when a slot frees up (max {game && 12} phones · 25 min each).</span>
            <Loader2 size={22} className="spin-slow" style={{ marginTop: 12, color: game.colorA }} />
          </div>
        )}

        {!configuring && phase === 'error' && (
          <div className="player-loading" data-testid="ovh-error"><p>Something went wrong.</p></div>
        )}

        {!configuring && phase === 'active' && (
          <>
            {error && (
              <div data-testid="ovh-active-error" className="player-loading">
                <p>{error}</p>
                <span className="player-loading-hint">Set your orchestrator URL under “Server”, then Reconnect.</span>
              </div>
            )}
            {!error && loading && (
              <div className="player-loading"><div className="spinner" /><p>Booting your phone &amp; launching Roblox...</p><span className="player-loading-hint">First boot installs the app — this can take a couple of minutes.</span></div>
            )}
            {!error && streamUrl && (
              <div style={{ position: 'relative', width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <div style={{ position: 'relative', height: '94%', aspectRatio: '9 / 16', maxWidth: '100%', borderRadius: 22, overflow: 'hidden', boxShadow: '0 20px 60px rgba(0,0,0,0.6)', border: '2px solid rgba(255,255,255,0.08)', background: '#000' }}>
                  <iframe
                    key={reloadKey}
                    ref={frameRef}
                    title={game.name}
                    src={streamUrl}
                    tabIndex={0}
                    onLoad={() => { setLoading(false); setTimeout(focusScreen, 400); }}
                    allow="autoplay; fullscreen; gamepad; accelerometer; gyroscope; clipboard-read; clipboard-write; microphone"
                    style={{ width: '100%', height: '100%', border: 'none', background: '#000' }}
                    className={loading ? 'loading' : ''}
                  />
                </div>
                {!loading && needFocus && (
                  <button data-testid="ovh-focus-overlay" onClick={focusScreen} style={focusBtnStyle}>
                    <Keyboard size={15} style={{ color: game.colorA }} /> Click to enable touch &amp; keyboard
                  </button>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

const inputStyle = { padding: '10px 12px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(0,0,0,0.4)', color: '#fff', fontSize: 13 };
const focusBtnStyle = { position: 'absolute', bottom: 18, left: '50%', transform: 'translateX(-50%)', display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(13,13,18,0.9)', color: '#fff', border: '1px solid rgba(255,255,255,0.14)', padding: '9px 16px', borderRadius: 999, fontSize: 13, cursor: 'pointer', backdropFilter: 'blur(8px)' };
