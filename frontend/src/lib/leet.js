// Light-touch leetspeak / censoring for site chrome text (not game titles)
export function leet(text) {
  if (!text) return text;
  return text
    .replace(/unblocked/gi, (m) => keepCase(m, 'unbl0cked'))
    .replace(/blocked/gi, (m) => keepCase(m, 'bl0cked'))
    .replace(/block/gi, (m) => keepCase(m, 'bl0ck'))
    .replace(/games/gi, (m) => keepCase(m, 'g4m3s'))
    .replace(/game/gi, (m) => keepCase(m, 'g4m3'));
}

function keepCase(src, repl) {
  return src[0] === src[0].toUpperCase()
    ? repl.charAt(0).toUpperCase() + repl.slice(1)
    : repl;
}
