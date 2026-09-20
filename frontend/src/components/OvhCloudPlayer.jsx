import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { X, Maximize, RotateCw, MonitorSmartphone, Keyboard, Link2 } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function OvhCloudPlayer({ game, onClose }) {
  const [url, setUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);
  const [needFocus, setNeedFocus] = useState(true);
  const [editing, setEditing] = useState(false);
  const [newUrl, setNewUrl] = useState('');
  const frameRef = useRef(null);
  const stageRef = useRef(null);

  const fetchUrl = useCallback(() => {
    axios.get(`${API}/ovh/vnc`).then(({ data }) => {
      setUrl(data.url || '');
      setLoading(true);
      if (!data.url) setEditing(true);
    }).catch(() => setUrl(''));
  }, []);

  useEffect(() => {
    fetchUrl();
    const onKey = (e) => { if (e.key === 'Escape' && !document.fullscreenElement) onClose(); };
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => { window.removeEventListener('keydown', onKey); document.body.style.overflow = ''; };
  }, [fetchUrl, onClose]);

  const src = url
    ? url + (url.includes('?') ? '&' : '?') + `resize=scale&reconnect=true&r=${reloadKey}`
    : null;

  const focusScreen = () => {
    if (frameRef.current) { frameRef.current.focus(); setNeedFocus(false); }
  };

  const goFullscreen = () => {
    const el = stageRef.current;
    if (el && el.requestFullscreen) el.requestFullscreen().then(() => { setTimeout(focusScreen, 300); });
  };

  const saveUrl = () => {
    const u = newUrl.trim();
    if (!u) return;
    axios.post(`${API}/ovh/vnc`, { url: u }).then(() => {
      setEditing(false); setNewUrl(''); setUrl(u); setLoading(true); setReloadKey((k) => k + 1);
    }).catch(() => {});
  };

  return (
    <div className="player-overlay" data-testid="ovh-player">
      <div className="player-bar">
        <div className="player-title">
          <span className="player-dot" style={{ background: game.colorA }} />
          {game.name} <span style={{ opacity: 0.5, fontWeight: 400, marginLeft: 6 }}>· OVH Cl0ud</span>
        </div>
        <div className="player-actions">
          <button onClick={() => setEditing((v) => !v)} title="Update stream link" data-testid="ovh-edit-btn">
            <Link2 size={16} /> Link
          </button>
          <button onClick={() => { setLoading(true); setReloadKey((k) => k + 1); }} title="Reconnect" data-testid="ovh-reload-btn">
            <RotateCw size={16} /> Reconnect
          </button>
          <button onClick={goFullscreen} title="Fullscreen" data-testid="ovh-fullscreen-btn">
            <Maximize size={16} /> Fullscreen
          </button>
          <button className="close" onClick={onClose} title="Close" data-testid="ovh-close-btn">
            <X size={16} /> Close
          </button>
        </div>
      </div>

      <div className="player-stage" ref={stageRef} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {editing && (
          <div className="player-loading" data-testid="ovh-edit-panel" style={{ maxWidth: 560 }}>
            <MonitorSmartphone size={38} style={{ color: game.colorA }} />
            <p>Paste your OVH noVNC stream link</p>
            <span className="player-loading-hint">
              OVH console tokens expire fast. Open your VNC console, copy the full <b>vnc_lite.html?path=...token...</b> URL and paste it here.
            </span>
            <div style={{ display: 'flex', gap: 8, marginTop: 14, width: '100%' }}>
              <input
                data-testid="ovh-url-input"
                value={newUrl}
                onChange={(e) => setNewUrl(e.target.value)}
                placeholder="https://compute.bhs6.cloud.ovh.net:6080/vnc_lite.html?path=%3Ftoken%3D..."
                style={{ flex: 1, padding: '10px 12px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(0,0,0,0.4)', color: '#fff', fontSize: 13 }}
              />
              <button onClick={saveUrl} data-testid="ovh-url-save" style={{ padding: '10px 18px', borderRadius: 10, border: 'none', background: game.colorA, color: '#111', fontWeight: 700, cursor: 'pointer' }}>
                Connect
              </button>
            </div>
          </div>
        )}

        {!editing && (
          <>
            {loading && (
              <div className="player-loading">
                <div className="spinner" />
                <p>Connecting to your OVH cl0ud phone...</p>
                <span className="player-loading-hint">
                  Streaming your self-hosted Android over noVNC. Touch, mouse and keyboard all work once connected.
                </span>
              </div>
            )}
            {src && (
              <div style={{ position: 'relative', width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <iframe
                  key={reloadKey}
                  ref={frameRef}
                  title={game.name}
                  src={src}
                  tabIndex={0}
                  onLoad={() => { setLoading(false); setTimeout(focusScreen, 400); }}
                  allow="autoplay; fullscreen; gamepad; accelerometer; gyroscope; clipboard-read; clipboard-write; microphone"
                  style={{ width: '100%', height: '100%', border: 'none', background: '#000' }}
                  className={loading ? 'loading' : ''}
                />
                {!loading && needFocus && (
                  <button
                    data-testid="ovh-focus-overlay"
                    onClick={focusScreen}
                    style={{ position: 'absolute', bottom: 18, left: '50%', transform: 'translateX(-50%)', display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(13,13,18,0.9)', color: '#fff', border: '1px solid rgba(255,255,255,0.14)', padding: '9px 16px', borderRadius: 999, fontSize: 13, cursor: 'pointer', backdropFilter: 'blur(8px)' }}
                  >
                    <Keyboard size={15} style={{ color: game.colorA }} /> Click here to enable touch &amp; keyboard
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
