// Aplica o tema salvo antes da pintura (evita "piscar"). Padrão: escuro.
(function () {
  var t = 'dark';
  try {
    var s = localStorage.getItem('centelha-tema');
    if (s === 'light' || s === 'dark') t = s;
  } catch (e) {}
  document.documentElement.setAttribute('data-theme', t);
})();
