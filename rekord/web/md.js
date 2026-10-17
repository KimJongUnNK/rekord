// Minimal, safe Markdown renderer (escapes HTML first). Extras: [mm:ss] → seek links, [[id@mm:ss]] → recording links,
// "- [ ]" → checkboxes (data-line lets the app toggle and save them).
(function () {
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const toSec = (ts) => ts.split(":").reduce((a, b) => a * 60 + Number(b), 0);

  function inline(s) {
    s = esc(s);
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    s = s.replace(/\[\[([a-f0-9]{6,32})@((?:\d+:)?\d{1,2}:\d{2})\]\]/g,
      (_, id, ts) => `<a class="cite" href="#/r/${id}?t=${toSec(ts)}">${ts}</a>`);
    s = s.replace(/\[((?:\d+:)?\d{1,2}:\d{2})(?:\s*[–-]\s*(?:\d+:)?\d{1,2}:\d{2})?\]/g,
      (m, ts) => `<a class="tsl" data-t="${toSec(ts)}">${m.slice(1, -1)}</a>`);
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g, "$1<em>$2</em>");
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    return s;
  }

  function render(src) {
    const lines = String(src || "").replace(/\r/g, "").split("\n");
    let html = "", i = 0;
    const listStack = [];
    const closeLists = (depth = 0) => { while (listStack.length > depth) html += `</${listStack.pop().tag}>`; };
    while (i < lines.length) {
      const raw = lines[i], line = raw.trimEnd();
      if (/^```/.test(line)) {
        closeLists();
        let code = ""; i++;
        while (i < lines.length && !/^```/.test(lines[i])) code += esc(lines[i++]) + "\n";
        html += `<pre><code>${code}</code></pre>`; i++; continue;
      }
      if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
        closeLists();
        const cells = (l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => inline(c.trim()));
        html += "<table><thead><tr>" + cells(line).map((c) => `<th>${c}</th>`).join("") + "</tr></thead><tbody>";
        i += 2;
        while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) {
          html += "<tr>" + cells(lines[i]).map((c) => `<td>${c}</td>`).join("") + "</tr>"; i++;
        }
        html += "</tbody></table>"; continue;
      }
      let m;
      if ((m = line.match(/^(#{1,4})\s+(.*)$/))) { closeLists(); const n = Math.min(m[1].length, 3); html += `<h${n}>${inline(m[2])}</h${n}>`; i++; continue; }
      if (/^\s*([-*_])\s*\1\s*\1[\s\1]*$/.test(line)) { closeLists(); html += "<hr>"; i++; continue; }
      if ((m = line.match(/^>\s?(.*)$/))) { closeLists(); html += `<blockquote>${inline(m[1])}</blockquote>`; i++; continue; }
      if ((m = line.match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/))) {
        const depth = Math.floor(m[1].replace(/\t/g, "  ").length / 2) + 1;
        const tag = /\d/.test(m[2]) ? "ol" : "ul";
        while (listStack.length > depth) html += `</${listStack.pop().tag}>`;
        while (listStack.length < depth) { listStack.push({ tag }); html += `<${tag}>`; }
        const t = m[3].match(/^\[( |x|X)\]\s+(.*)$/);
        if (t) {
          const done = t[1] !== " ";
          html += `<li class="task${done ? " done" : ""}"><input type="checkbox" data-line="${i}"${done ? " checked" : ""}><span>${inline(t[2])}</span></li>`;
        } else html += `<li>${inline(m[3])}</li>`;
        i++; continue;
      }
      if (!line.trim()) { closeLists(); i++; continue; }
      closeLists();
      let para = inline(line); i++;
      while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|>|\s*([-*+]|\d+[.)])\s|```|\s*\|)/.test(lines[i])) para += "<br>" + inline(lines[i++].trimEnd());
      html += `<p>${para}</p>`;
    }
    closeLists();
    return html;
  }

  // toggles "- [ ]" on a given source line, returns new source
  function toggleTask(src, lineNo) {
    const lines = String(src).split("\n");
    const l = lines[lineNo];
    if (l) lines[lineNo] = /\[ \]/.test(l) ? l.replace("[ ]", "[x]") : l.replace(/\[(x|X)\]/, "[ ]");
    return lines.join("\n");
  }

  // nested list → tree for the mind map
  function outline(src) {
    const root = { text: "", children: [] };
    const stack = [{ depth: -1, node: root }];
    for (const raw of String(src).split("\n")) {
      const m = raw.match(/^(\s*)(?:[-*+]|\d+[.)])\s+(.*)$/) || raw.match(/^(#{1,4})\s+(.*)$/);
      if (!m) continue;
      const depth = m[1].startsWith("#") ? m[1].length - 1 : Math.floor(m[1].replace(/\t/g, "  ").length / 2);
      const node = { text: m[2].replace(/\*\*/g, "").replace(/\[[^\]]*\]/g, "").trim(), children: [] };
      while (stack.length && stack[stack.length - 1].depth >= depth) stack.pop();
      stack[stack.length - 1].node.children.push(node);
      stack.push({ depth, node });
    }
    return root.children.length === 1 ? root.children[0] : { text: "Gespräch", children: root.children };
  }

  window.MD = { render, toggleTask, outline, toSec };
})();
