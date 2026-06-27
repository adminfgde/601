/* 暗黑复习站 · 课程渲染引擎 */
(function () {
  "use strict";

  var dataEl = document.getElementById("course-data");
  if (!dataEl) return;
  var COURSE = JSON.parse(dataEl.textContent);

  // -- KaTeX protection --
  var MATH_OPEN = "\u0001MATH", MATH_CLOSE = "\u0001";
  function protectMath(md) {
    var store = [];
    md = md.replace(/\$\$([\s\S]+?)\$\$/g, function (m, tex) {
      store.push({ display: true, tex: tex });
      return MATH_OPEN + (store.length - 1) + MATH_CLOSE;
    });
    md = md.replace(/(^|[^\\$])\$([^\$\n]+?)\$/g, function (m, pre, tex) {
      store.push({ display: false, tex: tex });
      return pre + MATH_OPEN + (store.length - 1) + MATH_CLOSE;
    });
    return { md: md, store: store };
  }
  function sanitizeTex(tex) {
    return tex.replace(/\\%/g, "\u0001PCT").replace(/%/g, "\\%").replace(/\u0001PCT/g, "\\%");
  }
  function restoreMath(html, store) {
    return html.replace(new RegExp(MATH_OPEN + "(\\d+)" + MATH_CLOSE, "g"), function (m, i) {
      var item = store[+i];
      if (!item) return m;
      try {
        return window.katex.renderToString(sanitizeTex(item.tex), {
          displayMode: item.display, throwOnError: false, strict: false, output: "html"
        });
      } catch (e) {
        return '<code>' + escapeHtml(item.tex) + '</code>';
      }
    });
  }
  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // -- markmap --
  function markmapToHtml(src) {
    var lines = src.split("\n"), out = ['<div class="markmap-outline">'];
    var listOpen = false;
    lines.forEach(function (ln) {
      var hm = ln.match(/^(#{1,6})\s+(.*)$/);
      if (hm) {
        if (listOpen) { out.push("</ul>"); listOpen = false; }
        out.push('<div class="mm-h" style="margin-left:' + (hm[1].length - 1) * 14 + 'px">' + escapeHtml(hm[2]) + "</div>");
        return;
      }
      var lm = ln.match(/^(\s*)[-*+]\s+(.*)$/);
      if (lm) {
        if (!listOpen) { out.push("<ul>"); listOpen = true; }
        out.push('<li style="margin-left:' + lm[1].length * 6 + 'px">' + escapeHtml(lm[2]) + "</li>");
        return;
      }
      if (ln.trim() && !listOpen) out.push("<div>" + escapeHtml(ln) + "</div>");
    });
    if (listOpen) out.push("</ul>");
    out.push("</div>");
    return out.join("\n");
  }

  // -- marked renderer --
  var mermaidSeq = 0;
  function buildRenderer() {
    var r = new marked.Renderer();
    r.code = function (code, infostring) {
      var lang = (infostring || "").trim().split(/\s+/)[0];
      if (lang === "mermaid") return '<div class="mermaid">' + escapeHtml(code) + "</div>";
      if (lang === "markmap") return markmapToHtml(code);
      return "<pre><code>" + escapeHtml(code) + "</code></pre>";
    };
    r.image = function (href, title, text) {
      var alt = text || "";
      return '<img src="' + href + '" alt="' + escapeHtml(alt) + '" loading="lazy" ' +
        'onerror="this.outerHTML=&quot;<span class=\\&quot;img-missing\\&quot;>\u25a4 ' + escapeHtml(alt || href) + '</span>&quot;">';
    };
    return r;
  }
  var RENDERER = buildRenderer();
  marked.setOptions({ gfm: true, breaks: false, headerIds: false, mangle: false });

  // -- protect inline ~ and < --
  var TILDE_HOLD = "\u0001TLD";
  function protectInline(md) {
    var parts = md.split(/(```[\s\S]*?```|`[^`\n]*`)/g);
    for (var i = 0; i < parts.length; i += 2) {
      parts[i] = parts[i]
        .replace(/(^|[^~])~(?!~)/g, "$1" + TILDE_HOLD)
        .replace(/<(?![A-Za-z\/!?])/g, "&lt;");
    }
    return parts.join("");
  }
  function renderMarkdown(md) {
    var p = protectMath(md);
    var html = marked.parse(protectInline(p.md), { renderer: RENDERER });
    html = html.split(TILDE_HOLD).join("~");
    return restoreMath(html, p.store);
  }

  function runDynamic(container) {
    var nodes = container.querySelectorAll(".mermaid");
    if (nodes.length && window.mermaid) {
      nodes.forEach(function (n, i) { n.id = "mmd-" + (mermaidSeq++) + "-" + i; });
      try { window.mermaid.run({ nodes: nodes }); } catch (e) {}
    }
  }

  // -- DOM refs --
  var elSidebar = document.getElementById("sidebar");
  var elContent = document.getElementById("content");
  var elSearch = document.getElementById("search-input");

  // -- build nav --
  var GROUP_ORDER = ["章节精讲", "考前综合", "考前精华", "总览资料", "真题与网络资源", "期末冲刺", "原始课件", "导览", "复习资料", "例题精解", "章节素材", "学习系统", "知识图谱", "原始课件页图", "原始课件PDF"];
  var sectionsById = {};
  COURSE.sections.forEach(function (s) { sectionsById[s.id] = s; });

  function buildNav() {
    var groups = {};
    COURSE.sections.forEach(function (s) { (groups[s.group] = groups[s.group] || []).push(s); });
    var order = GROUP_ORDER.filter(function (g) { return groups[g]; });
    Object.keys(groups).forEach(function (g) { if (order.indexOf(g) < 0) order.push(g); });

    elSidebar.innerHTML = "";
    order.forEach(function (g) {
      var gdiv = document.createElement("div");
      gdiv.className = "group";
      var gt = document.createElement("div");
      gt.className = "group-title";
      gt.textContent = g + "  (" + groups[g].length + ")";
      gdiv.appendChild(gt);
      groups[g].forEach(function (s) {
        var b = document.createElement("button");
        b.className = "nav-item";
        b.textContent = s.title;
        b.dataset.id = s.id;
        b.title = s.title;
        b.addEventListener("click", function () { selectSection(s.id); closeSidebarMobile(); });
        gdiv.appendChild(b);
      });
      elSidebar.appendChild(gdiv);
    });
  }

  var currentId = null;
  function selectSection(id, scrollToText) {
    var s = sectionsById[id];
    if (!s) return;
    currentId = id;
    Array.prototype.forEach.call(elSidebar.querySelectorAll(".nav-item"), function (b) {
      b.classList.toggle("active", b.dataset.id === id);
    });
    var active = elSidebar.querySelector(".nav-item.active");
    if (active) active.scrollIntoView({ block: "nearest" });

    elContent.innerHTML =
      '<div class="crumbs">' + escapeHtml(COURSE.title) + " / " + escapeHtml(s.group) + "</div>" +
      '<article class="doc" id="doc"></article>';
    var doc = document.getElementById("doc");
    doc.innerHTML = renderMarkdown(s.md);
    runDynamic(doc);
    window.scrollTo(0, 0);
    if (scrollToText) highlightAndScroll(doc, scrollToText);
    if (history.replaceState) history.replaceState(null, "", "#" + encodeURIComponent(id));
  }

  function highlightAndScroll(root, q) {
    var lower = q.toLowerCase();
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    var node;
    while ((node = walker.nextNode())) {
      var idx = node.nodeValue.toLowerCase().indexOf(lower);
      if (idx >= 0) {
        var range = document.createRange();
        range.setStart(node, idx); range.setEnd(node, idx + q.length);
        var mk = document.createElement("mark"); mk.className = "hit";
        try { range.surroundContents(mk); mk.scrollIntoView({ block: "center" }); } catch (e) {}
        return;
      }
    }
  }

  // -- search --
  function navFilter(q) {
    var lower = q.toLowerCase();
    Array.prototype.forEach.call(elSidebar.querySelectorAll(".group"), function (g) {
      var any = false;
      Array.prototype.forEach.call(g.querySelectorAll(".nav-item"), function (b) {
        var hit = !q || b.textContent.toLowerCase().indexOf(lower) >= 0;
        b.classList.toggle("hidden", !hit);
        if (hit) any = true;
      });
      g.classList.toggle("hidden", !any);
    });
  }

  function cleanSnippet(text) {
    return text.replace(/```[\s\S]*?```/g, " ").replace(/<\/?[a-zA-Z][^>]*>/g, " ")
      .replace(/&lt;\/?[a-zA-Z][^&]*?&gt;/g, " ").replace(/&[a-z]+;/g, " ")
      .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1").replace(/\[[ xX]?\]/g, " ")
      .replace(/^[\s>#*\-+|]+/gm, " ").replace(/[|#`*_~]/g, " ")
      .replace(/[-:]{2,}/g, " ").replace(/\s+/g, " ").trim();
  }

  function fullTextSearch(q) {
    var lower = q.toLowerCase(), results = [];
    COURSE.sections.forEach(function (s) {
      var hay = s.md.toLowerCase(), idx = hay.indexOf(lower), count = 0, from = 0;
      while (idx >= 0) { count++; from = idx + lower.length; idx = hay.indexOf(lower, from); if (count > 99) break; }
      if (count > 0) {
        var first = hay.indexOf(lower);
        var snip = cleanSnippet(s.md.substring(Math.max(0, first - 40), first + 80));
        results.push({ id: s.id, title: s.title, group: s.group, count: count, snip: snip });
      }
    });
    results.sort(function (a, b) { return b.count - a.count; });

    elContent.innerHTML = '<div class="crumbs">\u641c\u7d22 "' + escapeHtml(q) + '" \u00b7 \u547d\u4e2d ' + results.length + ' \u7bc7</div>' +
      '<div class="search-results" id="sr"></div>';
    var sr = document.getElementById("sr");
    if (!results.length) { sr.innerHTML = '<div class="empty">\u672a\u627e\u5230\u76f8\u5173\u5185\u5bb9</div>'; return; }
    results.forEach(function (r) {
      var b = document.createElement("button");
      b.className = "sr-item";
      b.innerHTML = '<div class="sr-title">' + escapeHtml(r.title) + ' <small>' + escapeHtml(r.group) + ' \u00b7 ' + r.count + ' \u5904</small></div>' +
        '<div class="sr-snip">\u2026' + escapeHtml(r.snip) + '\u2026</div>';
      b.addEventListener("click", function () { selectSection(r.id, q); });
      sr.appendChild(b);
    });
  }

  var searchTimer = null;
  if (elSearch) {
    elSearch.addEventListener("input", function () { navFilter(elSearch.value.trim()); clearTimeout(searchTimer); });
    elSearch.addEventListener("keydown", function (e) { if (e.key === "Enter") { var q = elSearch.value.trim(); if (q) fullTextSearch(q); } });
  }

  // -- print --
  var btnPrint = document.getElementById("btn-print");
  if (btnPrint) {
    btnPrint.addEventListener("click", function () {
      var root = document.getElementById("print-root");
      if (!root.dataset.built) {
        var html = '<h1>' + escapeHtml(COURSE.title) + ' \u00b7 \u5168\u65b9\u4f4d\u590d\u4e60</h1>';
        COURSE.sections.forEach(function (s) {
          html += '<article class="doc"><h1>' + escapeHtml(s.title) + '</h1>' + renderMarkdown(s.md) + '</article>';
        });
        root.innerHTML = html;
        runDynamic(root);
        root.dataset.built = "1";
        setTimeout(function () { window.print(); }, 600);
      } else { window.print(); }
    });
  }

  // -- mobile sidebar --
  var btnMenu = document.getElementById("btn-menu");
  var scrim = document.createElement("div");
  scrim.className = "scrim";
  document.body.appendChild(scrim);
  function closeSidebarMobile() { elSidebar.classList.remove("open"); scrim.classList.remove("show"); }
  if (btnMenu) btnMenu.addEventListener("click", function () {
    var open = elSidebar.classList.toggle("open");
    scrim.classList.toggle("show", open);
  });
  scrim.addEventListener("click", closeSidebarMobile);

  // -- init --
  if (window.mermaid) window.mermaid.initialize({ startOnLoad: false, theme: "dark", securityLevel: "loose" });
  if (window.katex) {} // ensure katex loaded

  buildNav();
  var hashId = decodeURIComponent((location.hash || "").replace(/^#/, ""));
  var startId = sectionsById[hashId] ? hashId : (COURSE.defaultSection || (COURSE.sections[0] && COURSE.sections[0].id));
  if (startId) selectSection(startId);
})();
