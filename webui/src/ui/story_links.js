// Shared navigation to missions present in Story's last localized publication.
(() => {
  const W = window.WebUI;
  const cache = new Map();
  function load(language) {
    const code = String(language || 'CN').toUpperCase();
    if (!cache.has(code)) {
      const root = `data/lang/${encodeURIComponent(code)}/`;
      const pending = Promise.all(['index.json', 'missions.json'].map(async (file) => {
        const response = await fetch(root + file);
        if (!response.ok) throw new Error(`Story ${file}: HTTP ${response.status}`);
        return response.json();
      })).then(([index, names]) => {
        const missions = new Map();
        for (const entry of index.entries || []) {
          if (entry.m && entry.k && !missions.has(entry.m)) missions.set(entry.m, {
            key: entry.k, name: names.missionNames?.[entry.m] || entry.m,
          });
        }
        return { language: code, missions };
      }).catch((error) => { cache.delete(code); throw error; });
      cache.set(code, pending);
      if (cache.size > 2) cache.delete(cache.keys().next().value);
    }
    return cache.get(code);
  }
  function resolve(publication, mission) {
    const target = publication?.missions.get(String(mission));
    if (!target) return null;
    const url = new URL(location.href);
    url.search = ''; url.hash = 'story';
    url.searchParams.set('lang', publication.language);
    url.searchParams.set('story', target.key);
    return { href: url.href, label: target.name };
  }
  W.storyLinks = { load, resolve };
})();
