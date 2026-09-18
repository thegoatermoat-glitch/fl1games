import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { X, Maximize, RotateCw, Smartphone, Clock, AlertTriangle } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Daily usage cap: 2 hours per user (tracked in localStorage, resets each day)
const DAILY_LIMIT = 2 * 60 * 60; // seconds
const USAGE_KEY = 'fl1nt_cloudphone_usage';

const today = () => new Date().toISOString().slice(0, 10);
function readUsage() {
  try {
    const u = JSON.parse(localStorage.getItem(USAGE_KEY) || 'null');
    if (u && u.date === today()) return u;
  } catch (e) { /* ignore */ }
  return { date: today(), used: 0 };
}
const writeUsage = (u) => localStorage.setItem(USAGE_KEY, JSON.stringify(u));
function fmt(sec) {
  sec = Math.max(0, Math.floor(sec));
  const h = String(Math.floor(sec / 3600)).padStart(2, '0');
  const m = String(Math.floor((sec % 3600) / 60)).padStart(2, '0');
  const s = String(sec % 60).padStart(2, '0');
  return `${h}:${m}:${s}`;
}

// Build an embeddable URL for iframe-based providers (nativebridge/appetize)
function buildEmbedUrl(game) {
  const t = (game.target || '').trim();
  if (!t) return null;
  if (t.startsWith('http')) return t;
  if (game.provider === 'appetize') {
    return `https://appetize.io/embed/${t}?device=pixel7&scale=auto&autoplay=true&orientation=portrait&screenOnly=true`;
  }
  return `https://nativebridge.io/embed/${t}?device=pixel7&scale=100`;
}

export default function CloudPhonePlayer({ game, onClose }) {
  const isGeelark = game.provider === 'geelark';
  const embedUrl = isGeelark ? null : buildEmbedUrl(game);

  const [usage] = useState(readUsage);
  const [remaining, setRemaining] = useState(DAILY_LIMIT - usage.used);
  const [ended, setEnded] = useState(false); // 'limit' | 'closed' | false
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);

  // GeeLark session state
  const [streamUrl, setStreamUrl] = useState(embedUrl);
  const [starting, setStarting] = useState(isGeelark);
  const [error, setError] = useState(null);

  const frameRef = useRef(null);
  const usedRef = useRef(usage.used);
  const tickRef = useRef(null);
  const phoneIdRef = useRef(null);

  const blocked = remaining <= 0;
  const configured = isGeelark ? true : Boolean(embedUrl);

  const stopBackend = useCallback((useBeacon) => {
    if (!isGeelark) return;
    const url = `${API}/cloudphone/stop`;
    const payload = JSON.stringify({ phoneId: phoneIdRef.current });
    if (useBeacon && navigator.sendBeacon) {
      navigator.sendBeacon(url, new Blob([payload], { type: 'application/json' }));
    } else {
      axios.post(url, { phoneId: phoneIdRef.current }).catch(() => {});
    }
  }, [isGeelark]);

  const stopSession = useCallback((reason, useBeacon) => {
    writeUsage({ date: today(), used: usedRef.current });
    if (frameRef.current) { try { frameRef.current.src = 'about:blank'; } catch (e) { /* ignore */ } }
    if (tickRef.current) { clearInterval(tickRef.current); tickRef.current = null; }
    stopBackend(useBeacon);
    if (reason) setEnded(reason);
  }, [stopBackend]);

  // Start GeeLark phone when opened (once, unless restarted)
  useEffect(() => {
    if (!isGeelark || blocked || ended) return;
    let cancelled = false;
    setStarting(true); setError(null); setLoading(true);
    axios.post(`${API}/cloudphone/start`, {})
      .then(({ data }) => {
        if (cancelled) return;
        phoneIdRef.current = data.phoneId;
        if (data.streamUrl) setStreamUrl(data.streamUrl);
        else setError('The phone started but no stream URL was returned by the bridge.');
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.response?.data?.detail || 'Could not start the cl0ud phone.');
      })
      .finally(() => { if (!cancelled) setStarting(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadKey]);

  useEffect(() => {
    if (configured && blocked) setEnded('limit');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => { window.removeEventListener('keydown', onKey); document.body.style.overflow = ''; };
  }, [onClose]);

  // Count usage each second while active & visible
  useEffect(() => {
    if (!configured || ended) return;
    tickRef.current = setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      usedRef.current += 1;
      const rem = DAILY_LIMIT - usedRef.current;
      setRemaining(rem);
      if (usedRef.current % 5 === 0) writeUsage({ date: today(), used: usedRef.current });
      if (rem <= 0) stopSession('limit');
    }, 1000);
    return () => { if (tickRef.current) clearInterval(tickRef.current); };
  }, [configured, ended, reloadKey, stopSession]);

  // Stop the session when the tab is hidden / closed
  useEffect(() => {
    const onHide = () => { if (document.visibilityState === 'hidden') stopSession('closed', true); };
    const onUnload = () => stopSession(null, true);
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

  const goFullscreen = () => { const el = frameRef.current; if (el && el.requestFullscreen) el.requestFullscreen(); };
  const restart = () => { if (blocked) return; setEnded(false); setError(null); setLoading(true); setReloadKey((k) => k + 1); };
  const handleClose = () => { stopSession(); onClose(); };

  const lowTime = remaining <= 300 && remaining > 0;
  const showStage = configured && !ended;

  return (
    <div className="player-overlay">
      <div className="player-bar">
        <div className="player-title">
          <Smartphone size={18} style={{ color: game.colorA }} />
          {game.name}
        </div>
        <div className="player-actions">
          {showStage && (
            <span className={`session-timer ${lowTime ? 'low' : ''}`} title="Daily time remaining">
              <Clock size={14} /> {fmt(remaining)} left
            </span>
          )}
          <button onClick={restart} title="Restart" disabled={blocked}><RotateCw size={16} /> Restart</button>
          <button onClick={goFullscreen} title="Fullscreen"><Maximize size={16} /> Fullscreen</button>
          <button className="close" onClick={handleClose} title="Close"><X size={16} /> Close</button>
        </div>
      </div>

      <div className="player-stage">
        {ended ? (
          <div className="player-loading">
            <AlertTriangle size={40} style={{ color: 'var(--accent)' }} />
            <p>{ended === 'limit' ? 'Daily 2-hour limit reached' : 'Session stopped'}</p>
            <span className="player-loading-hint">
              {ended === 'limit'
                ? 'You have used your 2 hours of cl0ud phone time for today. It resets tomorrow.'
                : 'The session stopped because the tab was hidden or closed. Reopen to continue.'}
            </span>
          </div>
        ) : error ? (
          <div className="player-loading">
            <AlertTriangle size={40} style={{ color: 'var(--accent)' }} />
            <p>Cl0ud phone unavailable</p>
            <span className="player-loading-hint">{error}</span>
          </div>
        ) : (starting || loading) ? (
          <div className="player-loading">
            <div className="spinner" />
            <p>{starting ? 'Starting virtual Android phone...' : 'Booting Roblox...'}</p>
            <span className="player-loading-hint">
              Locked to Roblox only \u00b7 {fmt(remaining)} of daily time left
            </span>
          </div>
        ) : null}

        {showStage && streamUrl && !error && (
          <iframe
            key={reloadKey}
            ref={frameRef}
            title={game.name}
            src={streamUrl}
            onLoad={() => setLoading(false)}
            allow="autoplay; fullscreen; gamepad; accelerometer; gyroscope; clipboard-write; microphone; camera"
            className={(starting || loading) ? 'loading' : ''}
          />
        )}
      </div>
    </div>
  );
}
