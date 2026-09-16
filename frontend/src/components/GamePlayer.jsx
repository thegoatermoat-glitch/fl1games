import React, { useState, useEffect, useRef } from 'react';
import { X, Maximize, RotateCw, ExternalLink } from 'lucide-react';

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

  const src = game.type === 'cloud'
    ? `/cloud/#${encodeURIComponent(game.target)}&r=${reloadKey}`
    : `${API}/games/${game.slug}/play?r=${reloadKey}`;

  const isCloud = game.type === 'cloud';

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
        {loading && (
          <div className="player-loading">
            <div className="spinner" />
            <p>Loading {game.name}...</p>
            <span className="player-loading-hint">
              {isCloud
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
      </div>
    </div>
  );
}
