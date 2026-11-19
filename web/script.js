(function () {
  'use strict';

  // ---------- Authentification ----------
  // Session par cookie côté serveur : tous les fetch existants envoient le cookie tout seuls.
  // Routes attendues : GET /api/v1/auth/me  ·  POST /api/v1/auth/{login,register,logout,forgot}
  const AUTH_API = '/api/v1/auth';
  const $auth = document.getElementById('auth');
  // Stockage du jeton CSRF
  let csrfToken = null;
  const auth = { user: null };
  const nativeFetch = window.fetch.bind(window);

  // Récupération du jeton CSRF auprès du serveur
  async function refreshCsrfToken() {
    const res = await nativeFetch(AUTH_API + '/csrf');

    if (!res.ok) {
      throw new Error('Impossible de récupérer le jeton CSRF.');
    }

    const data = await res.json();

    if (!data.csrf_token) {
      throw new Error('Le serveur n’a pas fourni de jeton CSRF.');
    }

    csrfToken = data.csrf_token;
  }

  // Ajout automatique du jeton CSRF aux requêtes qui modifient des données.
  window.fetch = async function (input, init = {}) {
    const method = (init.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();
    const options = { ...init };

    if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method)) {
      if (!csrfToken) {
        await refreshCsrfToken();
      }

      const headers = new Headers(input instanceof Request ? input.headers : undefined);

      new Headers(init.headers || {}).forEach((value, key) => {
        headers.set(key, value);
      });

      headers.set('X-CSRFToken', csrfToken);
      options.headers = headers;
    }

    const res = await nativeFetch(input, options);

    if (res.status === 401 && auth.user) {
      endSession('Votre session a expiré. Reconnectez-vous.');
    }

    return res;
  };

  function authShow(id, msg) {
    $auth.querySelectorAll('.a-view').forEach((v) => { v.hidden = v.id !== 'a-' + id; });
    $auth.querySelectorAll('.a-err').forEach((e) => { e.textContent = ''; });
    $auth.querySelectorAll('input').forEach((i) => i.removeAttribute('aria-invalid'));
    const ok = document.getElementById('a-ok');
    ok.hidden = !msg;
    ok.textContent = msg || '';
    $auth.hidden = false;
    const first = $auth.querySelector('#a-' + id + ' input');
    if (first) first.focus();
  }

  function authSetErr(input, text) {
    input.setAttribute('aria-invalid', 'true');
    input.closest('.a-field').querySelector('.a-err').textContent = text;
  }

  $auth.querySelectorAll('[data-go]').forEach((b) =>
    b.addEventListener('click', () => authShow(b.dataset.go)));

  $auth.querySelectorAll('[data-eye]').forEach((b) => b.addEventListener('click', () => {
    const input = document.getElementById(b.dataset.eye);
    const hidden = input.type === 'password';
    input.type = hidden ? 'text' : 'password';
    b.textContent = hidden ? 'Masquer' : 'Afficher';
  }));

  $auth.querySelectorAll('form').forEach((f) => f.addEventListener('submit', async (e) => {
    e.preventDefault();
    f.querySelectorAll('.a-err').forEach((x) => { x.textContent = ''; });
    f.querySelectorAll('input').forEach((i) => i.removeAttribute('aria-invalid'));

    const kind = f.dataset.form;
    const user = f.elements.user;
    const pass = f.elements.pass;
    const pass2 = f.elements.pass2;
    const formErr = f.querySelector('.a-form-err');
    let valid = true;

    if (!user.value.trim()) { authSetErr(user, "Entrez votre nom d'utilisateur."); valid = false; }
    if (pass && !pass.value) { authSetErr(pass, 'Entrez votre mot de passe.'); valid = false; }
    if (kind === 'register' && pass.value) {
      if (pass.value.length < 8) { authSetErr(pass, 'Utilisez au moins 8 caractères.'); valid = false; }
      else if (pass.value !== pass2.value) { authSetErr(pass2, 'Les mots de passe ne sont pas identiques.'); valid = false; }
    }
    if (!valid) { f.querySelector('[aria-invalid="true"]').focus(); return; }

    const btn = f.querySelector('.a-btn');
    btn.disabled = true;
    try {
      const body = {};
      if (kind === 'register') {
          body.name = user.value.trim();
      } else {
          body.username = user.value.trim();
      }
      if (pass) body.password = pass.value;
      const res = await fetch(AUTH_API + '/' + kind, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const data = await res.json().catch(() => ({}));

      if (res.ok) {
        if (kind === 'login') {
          f.reset();
          // Flask réinitialise la session après la connexion : récupérer un nouveau jeton.
          await refreshCsrfToken();
          await enterApp({ username: data.username || body.username });
        } else if (kind === 'register') {
          f.reset();
          authShow('login', 'Compte créé. Vous pouvez maintenant vous connecter.');
        } else {
          f.reset();
          authShow('login', 'Si ce compte existe, un lien de réinitialisation a été envoyé.');
        }
      } else if (res.status === 401) {
        formErr.textContent = "Nom d'utilisateur ou mot de passe incorrect.";
      } else if (res.status === 409) {
        authSetErr(user, "Ce nom d'utilisateur est déjà pris.");
      } else if (res.status === 429) {
        formErr.textContent = 'Trop de tentatives. Réessayez dans quelques minutes.';
      } else {
        formErr.textContent = data.error || 'Une erreur est survenue. Réessayez.';
      }
    } catch (err) {
      console.error(err);
      formErr.textContent = 'Serveur injoignable. Vérifiez votre connexion.';
    } finally {
      btn.disabled = false;
    }
  }));

  function enterApp(user) {
    auth.user = user;
    $auth.hidden = true;
    sideUser.textContent = user.username;
    return loadApp();
  }

  function endSession(msg) {
    auth.user = null;
    state.lists = [];
    state.tasks = [];
    state.view = 'myday';
    state.search = '';
    state.selectedId = null;
    searchInput.value = '';
    $main.replaceChildren();
    $detail.replaceChildren();
    $detail.hidden = true;
    $auth.querySelectorAll('form').forEach((f) => f.reset());
    authShow('login', msg);
  }

  // ---------- Icons (constant markup only, never user text) ----------
  const ICONS = {
    plus: '<path d="M12 5v14M5 12h14"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    star: '<path d="M12 3.8l2.5 5.1 5.6.8-4.1 4 1 5.6L12 16.6l-5 2.7 1-5.6-4.1-4 5.6-.8z"/>',
    starOn: '<path fill="currentColor" d="M12 3.8l2.5 5.1 5.6.8-4.1 4 1 5.6L12 16.6l-5 2.7 1-5.6-4.1-4 5.6-.8z"/>',
    calendar: '<rect x="4" y="5.5" width="16" height="14.5" rx="2"/><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4"/>',
    note: '<path d="M6 3.5h9.5L19.5 7.5V20.5H6z"/><path d="M9 11.5h7M9 15h5"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M5.3 18.7l1.8-1.8M16.9 7.1l1.8-1.8"/>',
    list: '<path d="M9 6.5h11M9 12h11M9 17.5h11"/><path d="M4.5 6.5h.01M4.5 12h.01M4.5 17.5h.01"/>',
    inbox: '<path d="M3.5 13.5l2.2-7h12.6l2.2 7v5.5h-17z"/><path d="M3.5 13.5h4.5l1 2h6l1-2h4.5"/>',
    chevron: '<path d="M6 9.5l6 6 6-6"/>',
    trash: '<path d="M4.5 6.5h15M9.5 6.5V4.5h5v2M6.5 6.5l1 13h9l1-13"/>',
    close: '<path d="M6 6l12 12M18 6L6 18"/>',
    search: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>'
  };

  const SMART = [
    { key: 'myday', label: 'Ma journée', icon: 'sun' },
    { key: 'important', label: 'Important', icon: 'star' },
    { key: 'planned', label: 'Planifié', icon: 'calendar' },
    { key: 'all', label: 'Tâches', icon: 'inbox' }
  ];
  const SMART_KEYS = SMART.map((v) => v.key);
  const THEMES = ['violet', 'ocre', 'petrole'];
  const SORTS = [
    ['created', "Date d'ajout"],
    ['due', 'Échéance'],
    ['important', 'Importance'],
    ['alpha', 'Alphabétique']
  ];
  const DATE_SHORT = new Intl.DateTimeFormat('fr-FR', { weekday: 'short', day: 'numeric', month: 'short' });
  const DATE_LONG = new Intl.DateTimeFormat('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });
  const DATE_DAY_MONTH = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long' });
  const UNDO_MS = 6000;

  // ---------- State ----------
  const state = {
    lists: [],
    tasks: [],
    view: 'myday',
    search: '',
    selectedId: null,
    doneOpen: true,
    sort: JSON.parse(localStorage.getItem('sort') || '{}'),
    popId: null
  };
  const uid = (prefix) => prefix + crypto.randomUUID();
  let undoAction = null;
  let toastTimer = null;
  let focusBackup = null;

  // ---------- DOM helpers ----------
  // Creates elements with the DOM API; user text only ever goes in as text nodes or .value.
  function el(tag, props, ...kids) {
    const node = document.createElement(tag);
    for (const child of kids.flat()) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    for (const key of Object.keys(props || {})) {
      const v = props[key];
      if (v === null || v === undefined || v === false) continue;
      if (key == 'class') node.setAttribute('class', v);
      else if (key == 'text') node.textContent = String(v);
      else if (key == 'value' || key == 'selected' || key == 'hidden') node[key] = v;
      else node.setAttribute(key, v === true ? '' : String(v));
    }
    return node;
  }

  function icon(name) {
    const tpl = document.createElement('template');
    tpl.innerHTML =
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' +
      ICONS[name] + '</svg>';
    return tpl.content.firstElementChild;
  }

  function autoSize(ta) {
    ta.style.height = 'auto';
    ta.style.height = ta.scrollHeight + 'px';
  }

  // ---------- Dates (local, never toISOString / UTC parsing) ----------
  const pad = (n) => String(n).padStart(2, '0');
  const toISO = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const parseISO = (s) => {
    const [y, m, d] = s.split('-').map(Number);
    return new Date(y, m - 1, d);
  };
  const todayISO = () => toISO(new Date());
  const addDays = (iso, n) => {
    const d = parseISO(iso);
    d.setDate(d.getDate() + n);
    return toISO(d);
  };
  const nextMonday = (iso) => {
    const d = parseISO(iso);
    const diff = ((1 - d.getDay() + 7) % 7) || 7;
    return addDays(iso, diff);
  };
  const fmtDue = (iso) => DATE_SHORT.format(parseISO(iso));
  const fmtCreated = (ts) => DATE_DAY_MONTH.format(new Date(ts));

  // ---------- Sample data ----------
  function seedSample() {
    const now = Date.now();
    const H = 3600 * 1000;
    const today = todayISO();
    state.lists = [
      { id: 'l1', name: 'Travail', theme: 'violet' },
      { id: 'l2', name: 'Maison', theme: 'ocre' },
      { id: 'l3', name: 'Courses', theme: 'petrole' }
    ];
    const defs = [
      { title: 'Répondre aux e-mails de l\'équipe', list: 'l1', due: today, myDay: true },
      { title: 'Préparer la réunion de lundi', list: 'l1', due: addDays(today, 7), note: 'Ordre du jour à envoyer la veille.',
        steps: [['Relire le compte rendu', true], ['Réserver la salle B', false]] },
      { title: 'Relire le contrat fournisseur', list: 'l1', important: true },
      { title: 'Envoyer la note de frais', list: 'l1', due: addDays(today, -2), note: 'Joindre les justificatifs du déplacement.' },
      { title: 'Lire le chapitre 4 du rapport', list: 'l1',
        steps: [['Prendre des notes', false], ['Résumer les points clés', false]] },
      { title: 'Appeler le plombier', list: 'l2', due: addDays(today, 1), note: 'Fuite sous l\'évier de la cuisine.' },
      { title: 'Ranger le garage', list: 'l2', due: addDays(today, 14) },
      { title: 'Arroser les plantes', list: 'l2', done: true },
      { title: 'Acheter du café', list: 'l3', myDay: true },
      { title: 'Acheter des pommes et des citrons', list: 'l3',
        steps: [['Pommes Gala', false], ['Citrons bio', false]] },
      { title: 'Acheter du pain', list: 'l3', done: true },
      { title: 'Passer à la pharmacie', list: 'l3', important: true }
    ];
    state.tasks = defs.map((d, i) => {
      const n = i + 1;
      return {
        id: 't' + n,
        title: d.title,
        done: !!d.done,
        important: !!d.important,
        myDay: !!d.myDay,
        due: d.due || null,
        listId: d.list,
        steps: (d.steps || []).map((s, j) => ({ id: 's' + n + '-' + j, title: s[0], done: s[1] })),
        note: d.note || '',
        createdAt: now - i * H,
        completedAt: d.done ? now - 2 * H : null
      };
    });
  }

  // ---------- Derived data ----------
  const searchQuery = () => state.search.trim();
  const sortFor = (key) => state.sort[key] || 'created';
  const findTask = (id) => state.tasks.find((t) => t.id == id) || null;
  const findRowEl = (id) => $main.querySelector('.task[data-id="' + id + '"]');

  function selectedTask() {
    const t = findTask(state.selectedId);
    if (!t) state.selectedId = null;
    return t;
  }

  function customList() {
    if (SMART_KEYS.includes(state.view)) return null;
    return state.lists.find((l) => String(l.id) == String(state.view)) || null;
  }

  function viewLabel(key) {
    const s = SMART.find((v) => v.key == key);
    if (s) return s.label;
    const l = state.lists.find((x) => x.id == key);
    return l ? l.name : '';
  }

  function themeName() {
    if (searchQuery()) return 'all';
    if (SMART_KEYS.includes(state.view)) return state.view;
    const l = customList();
    return l ? l.theme : 'all';
  }

  function inView(t, key) {
    switch (key) {
      case 'myday': return t.myDay;
      case 'important': return t.important;
      case 'planned': return !!t.due;
      case 'all': return true;
      default: return String(t.listId) == String(key);
    }
  }

  function scopeTasks(q) {
    if (q) {
      const lq = q.toLowerCase();
      return state.tasks.filter((t) =>
        t.title.toLowerCase().includes(lq) || t.note.toLowerCase().includes(lq));
    }
    return state.tasks.filter((t) => inView(t, state.view));
  }

  function openCount(key) {
    return state.tasks.filter((t) => !t.done && inView(t, key)).length;
  }

  function sortTasks(arr, key) {
    const byAdded = (a, b) => b.createdAt - a.createdAt;
    const cmp = {
      created: byAdded,
      due: (a, b) => {
        const x = a.due || '9999-12-31';
        const y = b.due || '9999-12-31';
        return x < y ? -1 : x > y ? 1 : byAdded(a, b);
      },
      important: (a, b) => (b.important - a.important) || byAdded(a, b),
      alpha: (a, b) => a.title.localeCompare(b.title, 'fr', { sensitivity: 'base' })
    }[key] || byAdded;
    return arr.slice().sort(cmp);
  }

  // ---------- Static shell (sidebar parts, persistent elements) ----------
  const $sidebar = document.getElementById('sidebar');
  const $main = document.getElementById('main');
  const $detail = document.getElementById('detail');
  const $toast = document.getElementById('toast');

  const searchInput = el('input', { class: 'search', type: 'search', placeholder: 'Rechercher', 'aria-label': 'Rechercher', autocomplete: 'off' });
  const sideHead = el('div', { class: 'side-head' }, searchInput);
  const navEl = el('nav', { class: 'nav' });
  const newListInput = el('input', { type: 'text', placeholder: 'Nouvelle liste', 'aria-label': 'Nouvelle liste', autocomplete: 'off' });
  const newListForm = el('form', { class: 'new-list' }, el('span', { class: 'nav-icon' }, icon('plus')), newListInput);

  // Utilisateur connecté + bouton de déconnexion (bas de la barre latérale)
  const sideUser = el('span', { class: 'side-user' });
  const logoutBtn = el('button', { class: 'side-logout', type: 'button' }, 'Se déconnecter');
  const sideFoot = el('div', { class: 'side-foot' }, sideUser, logoutBtn);
  logoutBtn.addEventListener('click', async () => {
    try {
      await fetch(AUTH_API + '/logout', { method: 'POST' });
    } catch (err) {
      console.error(err);
    }

    // La déconnexion réinitialise la session côté serveur.
    csrfToken = null;
    endSession();
  });

  const els = { header: null, scroll: null, add: null };

  // ---------- Sidebar ----------
  function navItem(key, label, iconName, count) {
    const active = key == state.view;
    return el('li', null,
      el('button', {
        class: 'nav-item' + (active ? ' is-active' : ''),
        type: 'button',
        'data-view': key,
        'aria-current': active ? 'page' : null
      },
        el('span', { class: 'nav-icon' }, icon(iconName)),
        el('span', { class: 'nav-label', text: label }),
        count > 0 ? el('span', { class: 'nav-count', text: String(count) }) : null));
  }

  function renderNav() {
    navEl.replaceChildren(
      el('ul', { class: 'nav-group' }, SMART.map((v) => navItem(v.key, v.label, v.icon, openCount(v.key)))),
      el('hr', { class: 'nav-sep' }),
      el('ul', { class: 'nav-group' }, state.lists.map((l) => navItem(l.id, l.name, 'list', openCount(l.id))))
    );
  }

  function updateNavLabel(id, name) {
    const label = navEl.querySelector('.nav-item[data-view="' + id + '"] .nav-label');
    if (label) label.textContent = name;
  }

  // ---------- Main ----------
  function buildHeader(q) {
    const list = q ? null : customList();
    const key = q ? 'search' : state.view;
    let titleWrap;
    if (list) {
      titleWrap = el('div', { class: 'view-title-wrap' },
        el('input', { class: 'view-title-input', type: 'text', 'aria-label': 'Nom de la liste', value: list.name, autocomplete: 'off' }));
    } else {
      const title = q ? 'Résultats pour « ' + q + ' »' : viewLabel(state.view);
      titleWrap = el('div', { class: 'view-title-wrap' },
        el('h1', { class: 'view-title', text: title }),
        (state.view == 'myday' && !q) ? el('p', { class: 'view-date', text: DATE_LONG.format(new Date()) }) : null);
    }
    const sortSel = el('select', { class: 'sort-select' },
      SORTS.map(([v, l]) => el('option', { value: v, selected: sortFor(key) == v }, l)));
    return el('header', { class: 'view-head' },
      el('button', { class: 'menu-btn icon-btn', type: 'button', 'aria-label': 'Ouvrir le menu' }, icon('menu')),
      titleWrap,
      el('label', { class: 'sort' }, el('span', { text: 'Trier' }), sortSel),
      list ? el('button', { class: 'delete-list icon-btn', type: 'button', 'aria-label': 'Supprimer la liste' }, icon('trash')) : null);
  }

  function renderMain() {
    const q = searchQuery();
    $main.dataset.theme = themeName();
    $detail.style.setProperty('--theme', getComputedStyle($main).getPropertyValue('--theme'));
    els.header = buildHeader(q);
    els.scroll = el('div', { class: 'task-scroll' });
    els.add.hidden = !!q;
    $main.replaceChildren(els.header, els.scroll, els.add);
    renderTasks();
  }

  function checkButton(done, cls, pop) {
    return el('button', {
      class: cls + (pop ? ' is-pop' : ''),
      type: 'button',
      role: 'checkbox',
      'aria-checked': String(!!done),
      'aria-label': done ? 'Marquer comme non terminée' : 'Marquer comme terminée'
    }, icon('check'));
  }

  function starButton(on) {
    return el('button', {
      class: 'star' + (on ? ' is-on' : ''),
      type: 'button',
      'aria-pressed': String(!!on),
      'aria-label': on ? 'Retirer des importantes' : 'Marquer comme importante'
    }, icon(on ? 'starOn' : 'star'));
  }

  function buildRow(task) {
    const today = todayISO();
    const selected = task.id == state.selectedId;
    const pop = task.done && task.id == state.popId;
    const showList = !!searchQuery() || !customList();
    const metas = [];
    if (showList) {
      const l = state.lists.find((x) => x.id == task.listId);
      if (l) metas.push(el('span', { class: 'meta', text: l.name }));
    }
    if (task.steps.length) {
      const doneSteps = task.steps.filter((s) => s.done).length;
      metas.push(el('span', { class: 'meta', text: doneSteps + ' sur ' + task.steps.length }));
    }
    if (task.due) {
      const overdue = !task.done && task.due < today;
      const isToday = task.due == today;
      const cls = 'meta' + (overdue ? ' is-overdue' : (isToday ? ' is-today' : ''));
      metas.push(el('span', { class: cls }, icon('calendar'), fmtDue(task.due)));
    }
    if (task.note.trim()) metas.push(el('span', { class: 'meta', title: 'Note' }, icon('note')));

    const cls = 'task' + (selected ? ' is-selected' : '') + (task.done ? ' is-done' : '');
    return el('li', { class: cls, 'data-id': task.id },
      checkButton(task.done, 'check', pop),
      el('button', { class: 'task-body', type: 'button' },
        el('span', { class: 'task-title', text: task.title }),
        metas.length ? el('span', { class: 'task-meta' }, metas) : null),
      starButton(task.important));
  }

  function buildEmpty(q) {
    let ic;
    let title;
    let text;
    if (q) {
      ic = 'search';
      title = 'Aucun résultat';
      text = 'Aucune tâche ne contient « ' + q + ' ».';
    } else {
      switch (state.view) {
        case 'myday':
          ic = 'sun';
          title = 'Votre journée est libre';
          text = 'Ajoutez une tâche ci-dessous pour planifier votre journée.';
          break;
        case 'important':
          ic = 'star';
          title = 'Rien d\'important pour l\'instant';
          text = 'Touchez l\'étoile d\'une tâche pour la retrouver ici.';
          break;
        case 'planned':
          ic = 'calendar';
          title = 'Aucune tâche planifiée';
          text = 'Les tâches avec une échéance apparaissent ici.';
          break;
        case 'all':
          ic = 'inbox';
          title = 'Aucune tâche';
          text = 'Ajoutez une tâche ci-dessous pour commencer.';
          break;
        default:
          ic = 'list';
          title = 'Cette liste est vide';
          text = 'Ajoutez votre première tâche ci-dessous.';
      }
    }
    return el('div', { class: 'empty' },
      el('span', { class: 'empty-icon' }, icon(ic)),
      el('h2', { text: title }),
      el('p', { text: text }));
  }

  function renderTasks() {
    const q = searchQuery();
    const key = q ? 'search' : state.view;
    const sortKey = sortFor(key);
    const scope = scopeTasks(q);
    const open = sortTasks(scope.filter((t) => !t.done), sortKey);
    const done = sortTasks(scope.filter((t) => t.done), sortKey);
    const today = todayISO();
    const tomorrow = addDays(today, 1);
    const nodes = [];

    if (state.view == 'planned' && !q) {
      const groups = [
        ['En retard', open.filter((t) => t.due < today)],
        ['Aujourd\'hui', open.filter((t) => t.due == today)],
        ['Demain', open.filter((t) => t.due == tomorrow)],
        ['Plus tard', open.filter((t) => t.due > tomorrow)]
      ];
      for (const [title, items] of groups) {
        if (!items.length) continue;
        nodes.push(el('h2', { class: 'group-title', text: title }),
          el('ul', { class: 'task-list' }, items.map((t) => buildRow(t))));
      }
    } else {
      nodes.push(el('ul', { class: 'task-list' }, open.map((t) => buildRow(t))));
    }

    if (done.length) {
      nodes.push(el('button', { class: 'done-toggle', type: 'button', 'aria-expanded': String(state.doneOpen) },
        icon('chevron'),
        el('span', { text: 'Terminées' }),
        el('span', { class: 'done-count', text: String(done.length) })));
      nodes.push(el('ul', { class: 'task-list done-list', hidden: !state.doneOpen },
        done.map((t) => buildRow(t))));
    }

    if (scope.length == 0) nodes.push(buildEmpty(q));

    els.scroll.replaceChildren(...nodes);
    state.popId = null;
  }

  // ---------- Detail panel ----------
  function buildStep(task, step) {
    return el('li', { class: 'step' + (step.done ? ' is-done' : ''), 'data-id': step.id },
      el('button', {
        class: 'check check-sm',
        type: 'button',
        role: 'checkbox',
        'aria-checked': String(step.done),
        'aria-label': step.done ? 'Marquer l\'étape comme non terminée' : 'Marquer l\'étape comme terminée'
      }, icon('check')),
      el('input', { class: 'step-input', type: 'text', value: step.title, 'aria-label': 'Étape', autocomplete: 'off' }),
      el('button', { class: 'step-del icon-btn', type: 'button', 'aria-label': 'Supprimer l\'étape' }, icon('close')));
  }

  function blurDetail() {
    const a = document.activeElement;
    if (a && $detail.contains(a) && typeof a.blur == 'function') a.blur();
  }

  function renderDetail() {
    blurDetail();
    const task = selectedTask();
    if (!task) {
      $detail.hidden = true;
      document.body.classList.remove('has-detail');
      $detail.replaceChildren();
      return;
    }
    document.body.classList.add('has-detail');
    $detail.hidden = false;

    const titleTa = el('textarea', { class: 'd-title', rows: '1', 'aria-label': 'Titre de la tâche', value: task.title });
    const steps = el('ul', { class: 'steps' }, task.steps.map((s) => buildStep(task, s)));
    const addStep = el('form', { class: 'add-step' },
      el('span', null, icon('plus')),
      el('input', { type: 'text', placeholder: 'Ajouter une étape', 'aria-label': 'Ajouter une étape', autocomplete: 'off' }));
    const dueInput = el('input', { class: 'd-due', type: 'date', value: task.due || '', 'aria-label': 'Échéance' });
    const chips = [
      ['today', 'Aujourd\'hui'],
      ['tomorrow', 'Demain'],
      ['next', 'Semaine prochaine'],
      ['none', 'Aucune']
    ].map(([k, l]) => el('button', { class: 'chip', type: 'button', 'data-due': k }, l));
    const listSel = el('select', { class: 'd-list', 'aria-label': 'Liste' },
      state.lists.map((l) => el('option', { value: l.id, selected: l.id == task.listId }, l.name)));
    const noteTa = el('textarea', { class: 'd-note', placeholder: 'Ajouter une note', 'aria-label': 'Note', rows: '4', value: task.note });

    $detail.replaceChildren(
      el('div', { class: 'detail-scroll' },
        el('section', { class: 'd-card d-title-row' },
          checkButton(task.done, 'check', false),
          titleTa,
          starButton(task.important)),
        el('section', { class: 'd-card' }, steps, addStep),
        el('section', { class: 'd-card' },
          el('button', { class: 'd-row d-myday' + (task.myDay ? ' is-on' : ''), type: 'button', 'aria-pressed': String(task.myDay) },
            icon('sun'),
            el('span', { text: task.myDay ? 'Dans Ma journée' : 'Ajouter à Ma journée' }))),
        el('section', { class: 'd-card' },
          el('label', { class: 'd-row' }, icon('calendar'), el('span', { text: 'Échéance' }), dueInput),
          el('div', { class: 'd-quick' }, chips),
          el('label', { class: 'd-row' }, icon('list'), el('span', { text: 'Liste' }), listSel)),
        el('section', { class: 'd-card' }, noteTa)),
      el('footer', { class: 'd-foot' },
        el('button', { class: 'icon-btn d-close', type: 'button', 'aria-label': 'Fermer le détail' }, icon('close')),
        el('span', { class: 'd-created', text: 'Créée le ' + fmtCreated(task.createdAt) }),
        el('button', { class: 'icon-btn d-delete', type: 'button', 'aria-label': 'Supprimer la tâche' }, icon('trash'))));
    autoSize(titleTa);
  }

  // ---------- Full render ----------
  function render(focusSel) {
    renderNav();
    renderMain();
    renderDetail();
    if (focusSel) {
      const n = document.querySelector(focusSel);
      if (n) n.focus();
    }
  }

  function refreshRow(id) {
    const old = findRowEl(id);
    const task = findTask(id);
    if (old && task) old.replaceWith(buildRow(task));
  }

  // ---------- Actions ----------
  function pickView(key) {
    blurDetail();
    console.log("Valeur reçue par pickView :", key);
    state.view = key;
    state.selectedId = null;
    state.search = '';
    searchInput.value = '';
    render();
  }

  function toggleDrawer() {
    document.body.classList.toggle('sidebar-open');
  }

  function closeDrawer() {
    document.body.classList.remove('sidebar-open');
  }

  function closeDetail() {
    blurDetail();
    state.selectedId = null;
    render();
  }

  async function toggleDone(task, focusSel) {
    const newDone = !task.done;
    const response = await fetch(`/api/v1/tasks/${task.id}`, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            done: newDone
        })
    });
    if (!response.ok) {
        console.error("Erreur lors de la mise à jour :", await response.json());
        return;
    }
    task.done = newDone;
    task.completedAt = task.done ? Date.now() : null;
    state.popId = task.done ? task.id : null;

    render(focusSel);
  }

  async function toggleStar(task, focusSel) {
    const newImportant = !task.important;
    const response = await fetch(`/api/v1/tasks/${task.id}`, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            important: newImportant
        })
    });
    if (!response.ok) {
        console.error("Erreur lors de la mise à jour de l'importance :", await response.json());
        return;
    }
    task.important = newImportant;
    render(focusSel);
  }

  async function toggleStep(task, li) {
    const step = task.steps.find((s) => s.id == li.dataset.id);
    if (!step) return;

    const newDone = !step.done;

    const response = await fetch(`/api/v1/tasks/${task.id}/steps/${step.id}`, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            done: newDone
        })
    });

    if (!response.ok) {
        console.error("Erreur lors de la mise à jour de la sous-tâche :", await response.json());
        return;
    }

    step.done = newDone;

    const fresh = buildStep(task, step);
    li.replaceWith(fresh);

    const check = fresh.querySelector('.check-sm');
    if (check) check.focus();

    refreshRow(task.id);
  }

  async function deleteStep(task, li) {
    const response = await fetch(`/api/v1/tasks/${task.id}/steps/${li.dataset.id}`, {
        method: 'DELETE'
    });

    if (!response.ok) {
        console.error("Erreur lors de la suppression de la sous-tâche");
        return;
    }

    task.steps = task.steps.filter((s) => s.id !== li.dataset.id);
    li.remove();
    refreshRow(task.id);

    const input = $detail.querySelector('.add-step input');
    if (input) input.focus();
  }

  function dueFromChip(key) {
    const today = todayISO();
    if (key == 'today') return today;
    if (key == 'tomorrow') return addDays(today, 1);
    if (key == 'next') return nextMonday(today);
    return null;
  }

  function hideToast() {
    clearTimeout(toastTimer);
    toastTimer = null;
    undoAction = null;
    $toast.classList.remove('is-visible');
    $toast.replaceChildren();
  }

  function showToast(msg, onUndo) {
    undoAction = onUndo;
    $toast.replaceChildren(
      el('span', { text: msg }),
      el('button', { class: 'toast-undo', type: 'button', text: 'Annuler' }));
    $toast.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(hideToast, UNDO_MS);
  }

  async function undo() {
    const fn = undoAction;
    hideToast();
    if (!fn) return;
    await fn();
    render();
  }

  async function deleteTask(task) {
    const response = await fetch(`/api/v1/tasks/${task.id}`, {
      method: 'DELETE'
    });
    if (!response.ok) {
      console.error("Erreur lors de la suppression :", response.status);
      return;
    }
    blurDetail();
    const idx = state.tasks.indexOf(task);
    state.tasks.splice(idx, 1);
    state.selectedId = null;
    showToast('Tâche supprimée', async () => {
      const response = await fetch(`/api/v1/tasks/${task.id}/restore`, {
        method: 'POST'
      });

      if (!response.ok) {
          console.error("Erreur lors de la restauration :", response.status);
          return;
      }
    state.tasks.splice(idx, 0, task);
    });
    render();
    }


async function deleteList(list) {
  const response = await fetch(`/api/v1/lists/${list.id}`, {
    method: 'DELETE'
  });

  if (!response.ok) {
    console.error("Erreur lors de la suppression de la liste :", response.status);
    return;
  }

  blurDetail();

  const listIdx = state.lists.indexOf(list);
  const removed = [];

  state.tasks.forEach((t, i) => {
    if (t.listId == list.id) removed.push([i, t]);
  });

  state.tasks = state.tasks.filter((t) => t.listId !== list.id);
  state.lists.splice(listIdx, 1);

  state.view = 'myday';
  state.selectedId = null;
  state.search = '';
  searchInput.value = '';

  showToast('Liste supprimée', async () => {
    const response = await fetch(`/api/v1/lists/${list.id}/restore`, {
      method: 'POST'
    });

    if (!response.ok) {
      console.error("Erreur lors de la restauration de la liste :", response.status);
      return;
    }

    state.lists.splice(listIdx, 0, list);
    removed.forEach(([i, t]) => state.tasks.splice(i, 0, t));
  });

  render();
}


  function newTask(title, listId) {
    return {
      id: uid('t'),
      title,
      done: false,
      important: false,
      myDay: false,
      due: null,
      listId,
      steps: [],
      note: '',
      createdAt: Date.now(),
      completedAt: null
    };
  }

  async function addTask(form) {
    const input = form.querySelector('input');
    const title = input.value.trim();
    if (!title) return;
    const custom = customList();
    const fallback = state.lists.length ? state.lists[0].id : null;
    console.log("state.view :", state.view, typeof state.view);
    console.log("IDs des listes :", state.lists.map(l => [l.id, typeof l.id]));
    console.log("customList :", customList());
    const task = {
        title: title,
        note: '',
        steps: [],
        listId: custom ? custom.id : null,
        myDay: state.view == 'myday',
        important: state.view == 'important',
        due: state.view == 'planned' ? todayISO() : null,
        done: false,
        createdAt: Date.now(),
        completedAt: null
    };
    const response = await fetch('/api/v1/tasks', {
      method: 'POST',
      headers: {
          'Content-Type': 'application/json'
      },
      body: JSON.stringify(task)
    });
    if (!response.ok) {
        console.error("Erreur lors de l'enregistrement de la tâche");
        return;
    }
    const savedTask = await response.json();
    task.id = savedTask.id;
    state.tasks.push(task);
    input.value = '';
    renderNav();
    renderTasks();
  }


async function addList(form) {
    const input = form.querySelector('input');
    const name = input.value.trim();

    if (!name) return;

    const theme = THEMES[state.lists.length % THEMES.length];

    // Envoyer la liste au serveur
    const response = await fetch('/api/v1/lists', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            name: name,
            theme: theme
        })
    });

    if (!response.ok) {
        console.error("Erreur lors de la création de la liste");
        return;
    }

    // Récupérer l'identifiant SQLite
    const savedList = await response.json();

    const list = {
        id: savedList.id,
        name: name,
        theme: theme
    };

    blurDetail();
    state.lists.push(list);
    state.view = list.id;
    state.selectedId = null;
    state.search = '';
    searchInput.value = '';
    input.value = '';
    closeDrawer();
    render();

    const titleInput = $main.querySelector('.view-title-input');
    if (titleInput) {
        titleInput.focus();
        titleInput.select();
    }
}


async function addStep(form) {
    const input = form.querySelector('input');
    const title = input.value.trim();
    if (!title) return;

    const task = selectedTask();
    if (!task) return;

    const step = { id: uid('s'), title, done: false };

    const response = await fetch(`/api/v1/tasks/${task.id}/steps`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        id: step.id,
        title: step.title
      })
    });

    if (!response.ok) {
      console.error("Erreur lors de la création de la sous-tâche :", response.status);
      return;
    }

    const result = await response.json();
    console.log("Sous-tâche créée :", result.step);

    const savedStep = result.step;

    task.steps.push(savedStep);
    input.value = '';

    const ul = $detail.querySelector('.steps');
    if (ul) ul.append(buildStep(task, savedStep));

    refreshRow(task.id);
  }

  async function onDetailClick(t) {
    const task = selectedTask();
    if (!task) return;
    const stepEl = t.closest('.step');
    if (stepEl && t.closest('.check-sm')) return toggleStep(task, stepEl);
    if (stepEl && t.closest('.step-del')) return deleteStep(task, stepEl);
    if (t.closest('.check')) return toggleDone(task, '#detail .d-title-row .check');
    if (t.closest('.star')) return toggleStar(task, '#detail .d-title-row .star');
    if (t.closest('.d-myday')) {
      task.myDay = !task.myDay;
      return render('#detail .d-myday');
    }
    const chip = t.closest('.chip');
    if (chip) {
      const newDue = dueFromChip(chip.dataset.due);

    const response = await fetch(`/api/v1/tasks/${task.id}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ due: newDue })
    });
    if (!response.ok) {
      console.error("Erreur lors de la mise à jour de la date :", response.status);
      return;
    }
      task.due = newDue;
      return render();
    }
    if (t.closest('.d-close')) return closeDetail();
    if (t.closest('.d-delete')) return deleteTask(task);
  }

  // ---------- Event delegation ----------

  // Gestion des formulaires
  document.addEventListener('submit', (e) => {
      const form = e.target;

      if (form.classList.contains('add-step')) {
          e.preventDefault();
          addStep(form);
      } else if (form.classList.contains('add-task')) {
          e.preventDefault();
          addTask(form);
      } else if (form.classList.contains('new-list')) {
          e.preventDefault();
          addList(form);
      }
  });

  // Gestion des clics
  document.addEventListener('click', (e) => {
    const t = e.target;
    if (t.closest('.menu-btn')) return toggleDrawer();
    if (t.closest('.scrim')) return closeDrawer();

    const nav = t.closest('.nav-item');
    if (nav && $sidebar.contains(nav)) {
      pickView(nav.dataset.view);
      closeDrawer();
      return;
    }

    if (t.closest('.done-toggle')) {
      state.doneOpen = !state.doneOpen;
      renderTasks();
      const btn = els.scroll.querySelector('.done-toggle');
      if (btn) btn.focus();
      return;
    }

    if (t.closest('.delete-list')) {
      const list = customList();
      if (list) deleteList(list);
      return;
    }

    if (t.closest('.toast-undo')) return undo();

    if (t.closest('#detail')) return onDetailClick(t);

    const row = t.closest('#main .task');
    if (row) {
      const id = row.dataset.id;
      const task = findTask(id);
      if (!task) return;
      if (t.closest('.check')) return toggleDone(task, '.task[data-id="' + id + '"] .check');
      if (t.closest('.star')) return toggleStar(task, '.task[data-id="' + id + '"] .star');
      if (t.closest('.task-body')) {
        blurDetail();
        state.selectedId = state.selectedId == id ? null : id;
        render('.task[data-id="' + id + '"] .task-body');
      }
    }
  });

  document.addEventListener('input', async (e) => {
    const t = e.target;
    if (t == searchInput) {
      state.search = t.value;
      renderMain();
      return;
    }
    if (t.classList.contains('view-title-input')) {
      const list = customList();
      if (list) {
        list.name = t.value;
        updateNavLabel(list.id, t.value);
      }
      return;
    }
    if (t.classList.contains('d-title')) {
      const task = selectedTask();
      if (!task) return;
      task.title = t.value;
      const row = findRowEl(task.id);
      const titleEl = row && row.querySelector('.task-title');
      if (titleEl) titleEl.textContent = t.value;
      autoSize(t);
      return;
    }
    if (t.classList.contains('step-input')) {
      const task = selectedTask();
      const li = t.closest('.step');
      const step = task && li ? task.steps.find((s) => s.id == li.dataset.id) : null;
      if (step) step.title = t.value;
      return;
    }
    if (t.classList.contains('d-note')) {
      const task = selectedTask();
      if (!task) return;
      const newNote = t.value;
      const response = await fetch(`/api/v1/tasks/${task.id}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ note: newNote })
      });
      if (!response.ok) {
        console.error("Erreur lors de la sauvegarde de la note :", response.status);
        return;
      }

      task.note = newNote;
    }
  });

document.addEventListener('change', async (e) => {
  const t = e.target;

  if (t.classList.contains('sort-select')) {
    state.sort[searchQuery() ? 'search' : state.view] = t.value;
    localStorage.setItem('sort', JSON.stringify(state.sort));
    renderTasks();
    return;
  }

  const task = selectedTask();
  if (!task) return;

  if (t.classList.contains('d-due')) {
    const newDue = t.value || null;

    const response = await fetch(`/api/v1/tasks/${task.id}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ due: newDue })
    });

    if (!response.ok) {
      console.error("Erreur lors de la mise à jour de la date :", response.status);
      return;
    }

    task.due = newDue;
    render('#detail .d-due');

  } else if (t.classList.contains('d-list')) {
    const newListId = t.value ? Number(t.value) : null;

    const response = await fetch(`/api/v1/tasks/${task.id}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ listId: newListId })
    });

    if (!response.ok) {
      console.error("Erreur lors du changement de liste :", response.status);
      return;
    }

    task.listId = newListId;
    render('#detail .d-list');
  }
});

document.addEventListener('focusin', (e) => {
    const t = e.target;

    if (t.classList.contains('view-title-input')) {
        const list = customList();
        focusBackup = list ? { kind: 'list', id: list.id, value: list.name } : null;

    } else if (t.classList.contains('step-input')) {
        const task = selectedTask();
        const li = t.closest('.step');
        const step = task && li
            ? task.steps.find((s) => s.id == li.dataset.id)
            : null;

        focusBackup = step ? {
            kind: 'step',
            taskId: task.id,
            id: step.id,
            value: step.title
        } : null;

    } else if (t.classList.contains('d-title')) {
        const task = selectedTask();
        focusBackup = task ? { kind: 'task', id: task.id, value: task.title } : null;
    }
});

  document.addEventListener('focusout', async (e) => {
    const t = e.target;
    if (!t.isConnected) return;

    const backup = focusBackup;
    focusBackup = null;

    if (t.classList.contains('view-title-input')) {
        const list = customList();
        if (!list) return;

        const name = t.value.trim();

        if (!name) {
            t.value = list.name;
            return;
        }

        const response = await fetch(`/api/v1/lists/${list.id}`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ name: name })
        });

        if (!response.ok) {
            console.error("Erreur lors de la modification de la liste :", response.status);
            t.value = list.name;
            return;
        }

        const result = await response.json();

        list.name = result.name;
        t.value = list.name;
        updateNavLabel(list.id, list.name);
        return;
    }

    if (t.classList.contains('d-title')) {
        const task = backup && backup.kind == 'task'
            ? findTask(backup.id)
            : selectedTask();

        if (!task) return;

        const oldTitle = backup && backup.kind == 'task'
            ? backup.value
            : task.title;

        const v = t.value.trim();

        if (!v) {
            task.title = oldTitle;
            t.value = oldTitle;
            autoSize(t);
            return;
        }

        try {
            const response = await fetch(`/api/v1/tasks/${task.id}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ title: v })
            });

            if (!response.ok) {
                throw new Error("Erreur lors de la modification du titre");
            }

            const result = await response.json();

            task.title = result.title;
            t.value = task.title;

        } catch (error) {
            console.error(error);
            task.title = oldTitle;
            t.value = oldTitle;
        }

        autoSize(t);
        refreshRow(task.id);
        return;
    }

    if (t.classList.contains('step-input')) {
        const task = backup && backup.kind == 'step'
            ? findTask(backup.taskId)
            : selectedTask();

        const li = t.closest('.step');

        if (!task || !li) return;

        const step = task.steps.find((s) => s.id == li.dataset.id);
        if (!step) return;

        const oldTitle = backup && backup.kind == 'step'
            ? backup.value
            : step.title;

        const v = t.value.trim();

        if (!v) {
            task.steps = task.steps.filter((s) => s !== step);
            li.remove();
            refreshRow(task.id);
            return;
        }

        try {
            const response = await fetch(
                `/api/v1/tasks/${task.id}/steps/${step.id}`,
                {
                    method: 'PATCH',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ title: v })
                }
            );

            if (!response.ok) {
                throw new Error("Erreur lors de la modification de la sous-tâche");
            }

            step.title = v;
            t.value = v;
            refreshRow(task.id);

        } catch (error) {
            console.error(error);
            step.title = oldTitle;
            t.value = oldTitle;
        }

        return;
    }

    if (t.classList.contains('d-note')) {
        const task = selectedTask();
        if (!task) return;

        task.note = t.value.trim();
        t.value = task.note;
        refreshRow(task.id);
    }
});

  document.addEventListener('keydown', (e) => {
    const t = e.target;
    if (e.key == 'Escape' && state.selectedId) {
      const id = state.selectedId;
      closeDetail();
      const row = findRowEl(id);
      const body = row && row.querySelector('.task-body');
      if (body) body.focus();
      return;
    }
    if (e.key == 'Enter' && !e.shiftKey && t.classList &&
        (t.classList.contains('d-title') || t.classList.contains('step-input') || t.classList.contains('view-title-input'))) {
      e.preventDefault();
      t.blur();
    }
  });

  // ---------- Init ----------
  async function loadApp() {
  // Récupérer les listes depuis SQLite
  const responseLists = await fetch('/api/v1/lists');

  if (!responseLists.ok) {
    console.error("Erreur lors du chargement des listes");
    return;
  }
  
  state.lists = await responseLists.json();
  
  // Récupérer les tâches depuis SQLite
  const responseTasks = await fetch('/api/v1/tasks');

  if (!responseTasks.ok) {
    console.error("Erreur lors du chargement des tâches");
    return;
  }

  const tasks = await responseTasks.json();

  state.tasks = tasks.map(task => ({
    ...task,
    steps: JSON.parse(task.steps || "[]")
  }));
  
  els.add = el('form', { class: 'add-task' },
      el('span', { class: 'add-icon' }, icon('plus')),
      el('input', { type: 'text', placeholder: 'Ajouter une tâche', 'aria-label': 'Ajouter une tâche', autocomplete: 'off' }));
    $sidebar.replaceChildren(sideHead, navEl, newListForm, sideFoot);
    render();
  }

  // Au chargement : session déjà ouverte ? sinon écran de connexion.
  async function init() {
    try {
      // Obtenir le jeton avant toute requête qui pourrait modifier des données.
      await refreshCsrfToken();

      const res = await nativeFetch(AUTH_API + '/me');
      if (res.ok) {
        await enterApp(await res.json());
        return;
      }
    } catch (err) {
      console.error(err);
    }
    authShow('login');
  }

  init();
})();
