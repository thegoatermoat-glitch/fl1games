import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { Search, Gamepad2, Star, Sparkles } from 'lucide-react';
import './App.css';
import './components/GamePlayer.css';
import ParticleField from './components/ParticleField';
import GameTile from './components/GameTile';
import GamePlayer from './components/GamePlayer';
import CloudPhonePlayer from './components/CloudPhonePlayer';
import { leet } from './lib/leet';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const PAGE = 60;

const CAT_ICONS = {};

function App() {
  const [games, setGames] = useState([]);
  const [total, setTotal] = useState(0);
  const [categories, setCategories] = useState([]);
  const [grandTotal, setGrandTotal] = useState(0);
  const [query, setQuery] = useState('');
  const [debounced, setDebounced] = useState('');
  const [category, setCategory] = useState('All');
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [playing, setPlaying] = useState(null);
  const [favs, setFavs] = useState(() => {
    try { return JSON.parse(localStorage.getItem('fl1nt_favs') || '[]'); } catch { return []; }
  });
  const sentinelRef = useRef(null);

  // load categories once
  useEffect(() => {
    axios.get(`${API}/categories`).then(({ data }) => {
      setCategories(data.categories);
      setGrandTotal(data.total);
    }).catch(() => {});
  }, []);

  // debounce search
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 280);
    return () => clearTimeout(t);
  }, [query]);

  const fetchGames = useCallback(async (skip) => {
    const params = { skip, limit: PAGE };
    if (debounced) params.q = debounced;
    if (category !== 'All') {
      if (category === 'Favorites') return null;
      params.category = category;
    }
    const { data } = await axios.get(`${API}/games`, { params });
    return data;
  }, [debounced, category]);

  // reset + fetch when filters change
  useEffect(() => {
    let active = true;
    setLoading(true);
    if (category === 'Favorites') {
      if (favs.length === 0) { setGames([]); setTotal(0); setLoading(false); return; }
      axios.get(`${API}/games`, { params: { limit: 400 } }).then(({ data }) => {
        if (!active) return;
        let list = data.games.filter((g) => favs.includes(g.slug));
        if (debounced) list = list.filter((g) => g.name.toLowerCase().includes(debounced.toLowerCase()));
        setGames(list); setTotal(list.length); setLoading(false);
      });
      return () => { active = false; };
    }
    fetchGames(0).then((data) => {
      if (!active || !data) return;
      setGames(data.games); setTotal(data.total); setLoading(false);
    }).catch(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [debounced, category, fetchGames, favs]);

  // infinite scroll
  useEffect(() => {
    if (category === 'Favorites') return;
    const el = sentinelRef.current;
    if (!el) return;
    const io = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && !loadingMore && games.length < total) {
        setLoadingMore(true);
        fetchGames(games.length).then((data) => {
          if (data) setGames((prev) => [...prev, ...data.games]);
          setLoadingMore(false);
        }).catch(() => setLoadingMore(false));
      }
    }, { rootMargin: '400px' });
    io.observe(el);
    return () => io.disconnect();
  }, [games.length, total, loadingMore, fetchGames, category]);

  const toggleFav = (slug) => {
    setFavs((prev) => {
      const next = prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug];
      localStorage.setItem('fl1nt_favs', JSON.stringify(next));
      return next;
    });
  };

  const chips = [
    { name: 'All', count: grandTotal },
    { name: 'Favorites', count: favs.length },
    ...categories,
  ];

  return (
    <div className="app-shell">
      <ParticleField />

      <div className="container">
        <div className="brand-row">
          <div className="brand-mark"><Gamepad2 size={26} /></div>
          <h1 className="title">fl1nt <span className="accent">g4m3s</span></h1>
        </div>
        <p className="subtitle">{leet(`${grandTotal || 300}+ unblocked games that actually load`)}</p>

        <div className="search-card">
          <div className="search-box">
            <Search size={20} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={leet('Search games...')}
              autoFocus
            />
          </div>
        </div>

        <div className="chips">
          {chips.map((c) => (
            <button
              key={c.name}
              className={`chip ${category === c.name ? 'active' : ''}`}
              onClick={() => setCategory(c.name)}
            >
              {c.name === 'Favorites' && <Star size={13} fill={category === 'Favorites' ? 'currentColor' : 'none'} />}
              {c.name === 'All' && <Sparkles size={13} />}
              {leet(c.name)}
              <span className="count">{c.count}</span>
            </button>
          ))}
        </div>

        {loading ? (
          <div className="state-msg"><div className="spinner" style={{ margin: '0 auto' }} /></div>
        ) : games.length === 0 ? (
          <div className="state-msg">
            {category === 'Favorites'
              ? 'No favorite g4m3s yet — tap the star on any game.'
              : `No g4m3s found for "${debounced}"`}
          </div>
        ) : (
          <>
            <div className="results-meta">Showing {games.length} of {total} g4m3s</div>
            <div className="grid">
              {games.map((g, i) => (
                <GameTile
                  key={g.slug}
                  game={g}
                  index={i}
                  onPlay={setPlaying}
                  isFav={favs.includes(g.slug)}
                  onToggleFav={toggleFav}
                />
              ))}
            </div>
            <div ref={sentinelRef} className="sentinel" />
            {loadingMore && <div className="state-msg"><div className="spinner" style={{ margin: '0 auto' }} /></div>}
          </>
        )}

        <div className="footer">fl1nt g4m3s &middot; g4m3s served straight from the backend</div>
      </div>

      {playing && (
        playing.type === 'cloudphone'
          ? <CloudPhonePlayer game={playing} onClose={() => setPlaying(null)} />
          : <GamePlayer game={playing} onClose={() => setPlaying(null)} />
      )}
    </div>
  );
}

export default App;
