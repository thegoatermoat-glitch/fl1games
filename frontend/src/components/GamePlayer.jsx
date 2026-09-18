import React, { useState, useEffect, useRef } from 'react';
import { X, Maximize, RotateCw, Smartphone } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function GamePlayer({ game, onClose }) {
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);
  const frameRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    setLoading(true);
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [game, onClose]);

  const goFullscreen = () => {
    const el = frameRef.current;
    if (el && el.requestFullscreen) el.requestFullscreen();
  };

  const isCloud = game.type === 'cloud' || game.type === 'appetize';
  const isAppetize = game.type === 'appetize';
  const appetizeConfigured = isAppetize && game.target;

  let src = null;
  if (isAppetize) {
    if (appetizeConfigured) {
      const embed = `https://appetize.io/embed/${game.target}?device=pixel7&scale=auto&autoplay=true&orientation=portrait&screenOnly=true`;
      src = `/cloud/#${encodeURIComponent(embed)}&r=${reloadKey}`;
    }
  } else if (game.type === 'cloud') {
    src = `/cloud/#${encodeURIComponent(game.target)}&r=${reloadKey}`;
  } else {
    src = `${API}/games/${game.slug}/play?r=${reloadKey}`;
  }

  return (
    <div className="player-overlay" ref={containerRef}>
      <div className="player-bar">
        <div className="player-title">
          <span className="player-dot" style={{ background: game.colorA }} />
          {game.name}
        </div>
        <div className="player-actions">
          <button onClick={() => { setLoading(true); setReloadKey((k) => k + 1); }} title="Restart">
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
        {isAppetize && !appetizeConfigured ? (
          <div className="player-loading">
            <Smartphone size={40} style={{ color: 'var(--accent)' }} />
            <p>Cl0ud phone not configured yet</p>
            <span className="player-loading-hint">
              An appetize.io publicKey for Roblox needs to be added before this virtual Android phone can boot.
            </span>
          </div>
        ) : (
          <>
            {loading && (
              <div className="player-loading">
                <div className="spinner" />
                <p>Booting {game.name}...</p>
                <span className="player-loading-hint">
                  {isAppetize
                    ? 'Streaming a virtual Android phone through the wisp pr0xy \u2014 locked to Roblox only'
                    : isCloud
                      ? 'Cl0ud gaming tunnels through the wisp pr0xy \u2014 this can take a while and may need a login'
                      : 'Larger g4m3s may take a few seconds'}
                </span>
              </div>
            )}
            <iframe
              key={reloadKey}
              ref={frameRef}
              title={game.name}
              src={src}
              onLoad={() => setLoading(false)}
              allow="autoplay; fullscreen; gamepad; accelerometer; gyroscope; pointer-lock; microphone"
              className={loading ? 'loading' : ''}
            />
          </>
        )}
      </div>
    </div>
  );
}
