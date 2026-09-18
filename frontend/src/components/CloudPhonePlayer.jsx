import React, { useState, useEffect, useRef, useCallback } from 'react';
import { X, Maximize, RotateCw, Smartphone, Clock, AlertTriangle } from 'lucide-react';

// Daily usage cap: 2 hours per user (tracked in localStorage, resets each day)
const DAILY_LIMIT = 2 * 60 * 60; // seconds
const USAGE_KEY = 'fl1nt_cloudphone_usage';

function today() {
  return new Date().toISOString().slice(0, 10);
}
function readUsage() {
  try {
    const u = JSON.parse(localStorage.getItem(USAGE_KEY) || 'null');
    if (u && u.date === today()) return u;
  } catch (e) { /* ignore */ }
  return { date: today(), used: 0 };
}
function writeUsage(u) {
  localStorage.setItem(USAGE_KEY, JSON.stringify(u));
}
function fmt(sec) {
  sec = Math.max(0, Math.floor(sec));
  const h = String(Math.floor(sec / 3600)).padStart(2, '0');
  const m = String(Math.floor((sec % 3600) / 60)).padStart(2, '0');
  const s = String(sec % 60).padStart(2, '0');
  return `${h}:${m}:${s}`;
}

// Build the provider embed URL from an appId or a full URL
function buildEmbedUrl(game) {
  const t = (game.target || '').trim();
  if (!t) return null;
  if (t.startsWith('http')) return t;
  const provider = game.provider || 'nativebridge';
  if (provider === 'nativebridge') {
    return `https://nativebridge.io/embed/${t}?device=pixel7&scale=100`;
  }
  if (provider === 'appetize') {
    return `https://appetize.io/embed/${t}?device=pixel7&scale=auto&autoplay=true&orientation=portrait&screenOnly=true`;
  }
  return t;
}

export default function CloudPhonePlayer({ game, onClose }) {
  const embedUrl = buildEmbedUrl(game);
  const configured = Boolean(embedUrl);

  const [usage] = useState(readUsage);
  const [remaining, setRemaining] = useState(DAILY_LIMIT - usage.used);
  const [ended, setEnded] = useState(false); // 'limit' | 'closed' | false
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);

  const frameRef = useRef(null);
  const usedRef = useRef(usage.used);
  const tickRef = useRef(null);

  const stopSession = useCallback((reason) => {
    // Persist usage and blank the iframe so streaming (and any paid minutes) stop
    writeUsage({ date: today(), used: usedRef.current });
    if (frameRef.current) {
      try { frameRef.current.src = 'about:blank'; } catch (e) { /* ignore */ }
    }
    if (tickRef.current) { clearInterval(tickRef.current); tickRef.current = null; }
    if (reason) setEnded(reason);
  }, []);

  // Block immediately if the daily 2h cap is already spent
  useEffect(() => {
    if (configured && remaining <= 0) setEnded('limit');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Escape to close + lock body scroll
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  // Count usage every second while active & tab visible
  useEffect(() => {
    if (!configured || ended) return;
    tickRef.current = setInterval(() => {
      if (document.visibilityState !== 'visible') return; // don't burn time in background
      usedRef.current += 1;
      const rem = DAILY_LIMIT - usedRef.current;
      setRemaining(rem);
      if (usedRef.current % 5 === 0) writeUsage({ date: today(), used: usedRef.current });
      if (rem <= 0) stopSession('limit');
    }, 1000);
    return () => { if (tickRef.current) clearInterval(tickRef.current); };
  }, [configured, ended, reloadKey, stopSession]);

  // Stop the session when the tab is closed / hidden
  useEffect(() => {
    const onHide = () => {
      if (document.visibilityState === 'hidden') stopSession('closed');
    };
    const onUnload = () => stopSession();
    document.addEventListener('visibilitychange', onHide);
    window.addEventListener('beforeunload', onUnload);
    window.addEventListener('pagehide', onUnload);
    return () => {
      document.removeEventListener('visibilitychange', onHide);
      window.removeEventListener('beforeunload', onUnload);
      window.removeEventListener('pagehide', onUnload);
      stopSession();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stopSession]);

  const goFullscreen = () => {
    const el = frameRef.current;
    if (el && el.requestFullscreen) el.requestFullscreen();
  };

  const restart = () => {
    if (remaining <= 0) return;
    setEnded(false);
    setLoading(true);
    setReloadKey((k) => k + 1);
  };

  const lowTime = remaining <= 300 && remaining > 0;

  return (
    <div className="player-overlay">
      <div className="player-bar">
        <div className="player-title">
          <Smartphone size={18} style={{ color: game.colorA }} />
          {game.name}
        </div>
        <div className="player-actions">
          {configured && !ended && (
            <span className={`session-timer ${lowTime ? 'low' : ''}`} title="Daily time remaining">
              <Clock size={14} /> {fmt(remaining)} left
            </span>
          )}
          <button onClick={restart} title="Restart" disabled={remaining <= 0}>
            <RotateCw size={16} /> Restart
          </button>
          <button onClick={goFullscreen} title="Fullscreen">
            <Maximize size={16} /> Fullscreen
          </button>
          <button className="close" onClick={onClose} title="Close">
            <X size={16} /> Close
          </button>
        </div>
      </div>

      <div className="player-stage">
        {!configured ? (
          <div className="player-loading">
            <Smartphone size={40} style={{ color: 'var(--accent)' }} />
            <p>Cl0ud phone not configured yet</p>
            <span className="player-loading-hint">
              A NativeBridge appId (with Roblox uploaded) needs to be added before this virtual Android phone can boot.
            </span>
          </div>
        ) : ended ? (
          <div className="player-loading">
            <AlertTriangle size={40} style={{ color: 'var(--accent)' }} />
            <p>{ended === 'limit' ? 'Daily 2-hour limit reached' : 'Session stopped'}</p>
            <span className="player-loading-hint">
              {ended === 'limit'
                ? 'You have used your 2 hours of cl0ud phone time for today. It resets tomorrow.'
                : 'The session was stopped because the tab was hidden or closed. Reopen to continue.'}
            </span>
          </div>
        ) : (
          <>
            {loading && (
              <div className="player-loading">
                <div className="spinner" />
                <p>Booting virtual Android phone...</p>
                <span className="player-loading-hint">Locked to Roblox only \u00b7 {fmt(remaining)} of daily time left</span>
              </div>
            )}
            <iframe
              key={reloadKey}
              ref={frameRef}
              title={game.name}
              src={embedUrl}
              onLoad={() => setLoading(false)}
              allow="autoplay; fullscreen; gamepad; accelerometer; gyroscope; clipboard-write; microphone; camera"
              className={loading ? 'loading' : ''}
            />
          </>
        )}
      </div>
    </div>
  );
}
