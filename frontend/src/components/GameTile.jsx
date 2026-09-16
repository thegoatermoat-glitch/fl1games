import React, { useState } from 'react';
import { Play, Star } from 'lucide-react';

export default function GameTile({ game, index, onPlay, isFav, onToggleFav }) {
  const [imgOk, setImgOk] = useState(Boolean(game.image));
  const bg = `linear-gradient(145deg, ${game.colorA}, ${game.colorB})`;
  const showImg = game.image && imgOk;
  return (
    <a
      className="tile"
      href={`#${game.slug}`}
      style={{ animationDelay: `${Math.min(index, 20) * 20}ms` }}
      onClick={(e) => { e.preventDefault(); onPlay(game); }}
    >
      <div className="tile-icon" style={{ background: bg }}>
        <Star
          size={18}
          className={`tile-fav ${isFav ? 'on' : ''}`}
          fill={isFav ? 'currentColor' : 'none'}
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); onToggleFav(game.slug); }}
        />
        {showImg ? (
          <img
            className="tile-img"
            src={game.image}
            alt={game.name}
            loading="lazy"
            onError={() => setImgOk(false)}
          />
        ) : (
          <span>{game.monogram}</span>
        )}
        <div className="tile-play"><Play size={30} fill="#fff" /></div>
      </div>
      <span className="tile-label">{game.name}</span>
    </a>
  );
}
