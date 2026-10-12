"""
Polyglot Explainer — explain any complex topic clearly IN ANY LANGUAGE,
powered by Apertus (Switzerland's sovereign open LLM).

Track 2B "Own Project" entry, Hack Apertus online hackathon (Oct 12–15 2026).

Apertus access:
    OpenAI-compatible chat-completions endpoint, configured via env vars.
    The HackApertus project-template mandates these exact names (read FIRST):
        LLM_API_KEY       - provider API key (REQUIRED for live mode)
        LLM_BASE_URL      - e.g. https://api.infomaniak.com/2/ai/<product>/openai/v1
                            (leave EMPTY until you have a real endpoint — the
                            "{product}" placeholder is NOT expanded by code)
        LLM_NAME          - e.g. swiss-ai/Apertus-v1.5-70B
    Legacy APERTUS_* names are accepted as fallbacks (APERTUS_API_KEY,
    APERTUS_BASE_URL, APERTUS_MODEL, APERTUS_TIMEOUT).

    When no API key is set, the app runs in clearly-labeled DEMO MODE with
    canned multilingual explanations. No API key is ever invented or
    hardcoded; every demo artifact is labeled simulated/demo.
"""
from __future__ import annotations

import os
from typing import Any

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# HackApertus template-mandated names take precedence; APERTUS_* fall back.
APERTUS_API_KEY = (
    os.environ.get("LLM_API_KEY") or os.environ.get("APERTUS_API_KEY", "")
)
APERTUS_BASE_URL = (
    os.environ.get("LLM_BASE_URL")
    or os.environ.get("APERTUS_BASE_URL", "")
).rstrip("/")
APERTUS_MODEL = os.environ.get("LLM_NAME") or os.environ.get(
    "APERTUS_MODEL", "swiss-ai/Apertus-v1.5-70B"
)
REQUEST_TIMEOUT = int(os.environ.get("APERTUS_TIMEOUT", "120"))

DEMO_MODE = not APERTUS_API_KEY

# In-memory cache keyed (topic, language, depth) — repeated queries cost
# nothing and return instantly. Single-container scope; FIFO trim at 200.
_CACHE: dict[tuple[str, str, str], str] = {}
_CACHE_MAX = 200


def _cache_get(key: tuple[str, str, str]) -> str | None:
    return _CACHE.get(key)


def _cache_put(key: tuple[str, str, str], explanation: str) -> None:
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = explanation


# ---------------------------------------------------------------------------
# Languages (seed set; Apertus itself covers 1,811 languages)
# ---------------------------------------------------------------------------
LANGUAGES = [
    {"code": "en", "name": "English"},
    {"code": "hi", "name": "Hindi"},
    {"code": "ta", "name": "Tamil"},
    {"code": "bn", "name": "Bengali"},
    {"code": "kn", "name": "Kannada"},
    {"code": "te", "name": "Telugu"},
    {"code": "ml", "name": "Malayalam"},
    {"code": "mr", "name": "Marathi"},
    {"code": "gu", "name": "Gujarati"},
    {"code": "fr", "name": "French"},
    {"code": "de", "name": "German"},
    {"code": "ja", "name": "Japanese"},
    {"code": "sw", "name": "Swahili"},
]

DEPTHS = {
    "eli5": (
        "Explain like I'm 5: very simple words, short sentences, a playful "
        "analogy. Keep it short (about 100-150 words)."
    ),
    "standard": (
        "Explain at a standard level: clear, structured, accessible to an "
        "educated non-expert. About 250-400 words."
    ),
    "deep": (
        "Deep dive: thorough, technical and precise, with details and examples "
        "an expert would appreciate. About 500-800 words."
    ),
}
_DEPTH_MAX_TOKENS = {"eli5": 600, "standard": 1200, "deep": 2200}

# ---------------------------------------------------------------------------
# Demo-mode canned explanations (clearly labeled, simulated content)
# ---------------------------------------------------------------------------
_DEMO_EXPLANATIONS: dict[tuple[str, str, str], str] = {
    ("photosynthesis", "hi", "eli5"): (
        "[SIMULATED DEMO OUTPUT — no live model was called]\n\n"
        "प्रकाश संश्लेषण (Photosynthesis) पेड़ों का खाना बनाने का तरीका है। "
        "पत्तियाँ सूरज की रोशनी को पकड़ती हैं, हवा से कार्बन डाइऑक्साइड लेती हैं, "
        "और जड़ों से पानी उठाती हैं। फिर यह तीनों चीज़ों से चीनी बनाती हैं — "
        "जैसे रसोई में आटा, पानी और धूप से रोटी बनना!"
    ),
    ("photosynthesis", "ta", "eli5"): (
        "[SIMULATED DEMO OUTPUT — no live model was called]\n\n"
        "ஒளிச்சேர்க்கை (Photosynthesis) என்பது செடிகள் தங்கள் உணவைத் "
        "தயாரிக்கும் முறை. இலைகள் சூரிய ஒளியைப் பிடிக்கின்றன, காற்றிலிருந்து "
        "கார்பன் டை ஆக்சைடை எடுத்து, வேர்கள் வழியாக நீரை உறிஞ்சுகின்றன. "
        "பிறகு இவற்றிலிருந்து சர்க்கரையை உருவாக்குகின்றன!"
    ),
    ("photosynthesis", "en", "standard"): (
        "[SIMULATED DEMO OUTPUT — no live model was called]\n\n"
        "Photosynthesis is the process by which plants convert light energy "
        "into chemical energy. Chlorophyll in the leaves captures photons, "
        "water absorbed by the roots is split, and carbon dioxide from the air "
        "is fixed into glucose (C6H12O6), releasing oxygen as a byproduct. "
        "It underpins nearly every food chain on Earth."
    ),
    ("black holes", "ja", "standard"): (
        "[SIMULATED DEMO OUTPUT — no live model was called]\n\n"
        "ブラックホールは、重力が非常に強いため光さえも逃げられない天体です。"
        "巨大な星が燃料を使い果たして崩壊すると形成され、中心には特異点があり、"
        "周囲には事象の地平線と呼ばれる境界があります。この境界を越えたものは"
        "二度と戻れません。"
    ),
    ("black holes", "fr", "eli5"): (
        "[SIMULATED DEMO OUTPUT — no live model was called]\n\n"
        "Un trou noir, c'est comme un aspirateur géant dans l'espace ! "
        "Il est tellement lourd et fort qu'il aspire tout, même la lumière. "
        "Une fois que quelque chose tombe dedans, ça ne peut plus ressortir. "
        "C'est comme tomber dans un puits sans fond."
    ),
    ("neural networks", "de", "deep"): (
        "[SIMULATED DEMO OUTPUT — no live model was called]\n\n"
        "Neuronale Netze sind parametrisierte Funktionsapproximatoren, die aus "
        "Schichten miteinander verbundener Einheiten (Neuronen) bestehen. Jedes "
        "Neuron berechnet eine gewichtete Summe seiner Eingaben plus Bias, gefolgt "
        "von einer nichtlinearen Aktivierungsfunktion. Das Training erfolgt via "
        "Backpropagation: Gradienten der Verlustfunktion werden per Kettenregel "
        "rückwärts propagiert, und Gewichte werden mit Verfahren wie Adam "
        "aktualisiert."
    ),
    ("neural networks", "sw", "eli5"): (
        "[SIMULATED DEMO OUTPUT — no live model was called]\n\n"
        "Mtandao wa neva (neural network) ni kama ubongo mdogo wa kompyuta! "
        "Una sehemu ndogo ndogo zinazoitwa 'neva' zinazojifunza kwa kuona "
        "mifano mingi. Kama mtoto anayejifunza kutambua paka kwa kuona picha "
        "nyingi za paka — ndivyo kompyuta inavyojifunza!"
    ),
}

_DEMO_FALLBACK_TMPL = (
    "[SIMULATED DEMO OUTPUT — no live model was called]\n\n"
    "This is a demo-mode explanation of '{topic}' in {language} at '{depth}' "
    "depth. Set LLM_API_KEY (or APERTUS_API_KEY) to get a real explanation "
    "from the Apertus model."
)


def _demo_explain(topic: str, language: str, depth: str) -> str:
    key = (topic.strip().lower(), language, depth)
    return _DEMO_EXPLANATIONS.get(key, _DEMO_FALLBACK_TMPL.format(
        topic=topic, language=language, depth=depth
    ))


# ---------------------------------------------------------------------------
# Live Apertus client (OpenAI-compatible chat completions)
# ---------------------------------------------------------------------------
def _live_explain(topic: str, language: str, depth: str) -> str:
    if not APERTUS_BASE_URL or "<" in APERTUS_BASE_URL:
        raise requests.RequestException(
            "LLM_BASE_URL is not a usable endpoint (empty or contains an "
            "unexpanded placeholder like <product>). Set it to a real "
            "OpenAI-compatible endpoint, e.g. the Infomaniak AI URL."
        )
    lang_name = next((l["name"] for l in LANGUAGES if l["code"] == language), language)
    depth_instr = DEPTHS.get(depth, DEPTHS["standard"])
    system = (
        "You are Polyglot Explainer, an explainer powered by Apertus, an open "
        "multilingual language model. Write the ENTIRE explanation in the "
        "requested language. No English preamble, no translations, no "
        "meta-commentary — just the explanation."
    )
    user = (
        f"Explain the topic '{topic}' in {lang_name}. "
        f"{depth_instr} Respond only with the explanation, written in {lang_name}."
    )
    resp = requests.post(
        f"{APERTUS_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {APERTUS_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": APERTUS_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.7,
            "max_tokens": _DEPTH_MAX_TOKENS.get(depth, 1200),
        },
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
_INDEX_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Polyglot Explainer — powered by Apertus</title>
<style>
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:760px;
margin:2rem auto;padding:0 1rem;color:#1a1a1a}
.badge{display:inline-block;padding:.15rem .6rem;border-radius:999px;font-size:.8rem;
font-weight:600}
.demo{background:#fff3cd;color:#7a5c00;border:1px solid #e6c860}
.live{background:#d4edda;color:#155724;border:1px solid #a3d9b1}
#topic{width:100%;padding:.6rem;font-size:1rem;border:1px solid #bbb;border-radius:6px}
.chips{display:flex;flex-wrap:wrap;gap:.4rem;margin:.6rem 0}
.chip{padding:.3rem .7rem;border:1px solid #888;border-radius:999px;cursor:pointer;font-size:.9rem}
.chip.sel{background:#0d6efd;color:#fff;border-color:#0d6efd}
select,button{padding:.55rem .9rem;font-size:1rem;border-radius:6px}
button{background:#0d6efd;color:#fff;border:none;cursor:pointer}
button:disabled{opacity:.5}
#result{white-space:pre-wrap;background:#f6f6f6;border:1px solid #ddd;border-radius:6px;
padding:1rem;margin-top:1rem;min-height:4rem}
.meta{font-size:.85rem;color:#555;margin-top:.4rem}
.err{color:#a00;font-weight:600}
footer{margin-top:2.5rem;font-size:.85rem;color:#666}
</style></head><body>
<h1>Polyglot Explainer</h1>
<p>Explain any complex topic clearly, <strong>in any language</strong> — powered by Apertus,
Switzerland's sovereign open LLM.</p>
<p><span class="badge {mode_class}">{mode_label}</span></p>
<form id="f">
<label for="topic"><strong>Topic</strong></label><br>
<input id="topic" name="topic" placeholder="e.g. photosynthesis, black holes, neural networks" required>
<div class="chips" id="chips"></div>
<label for="depth"><strong>Depth</strong></label><br>
<select id="depth" name="depth">
<option value="eli5">ELI5 — explain like I'm 5</option>
<option value="standard" selected>Standard — clear &amp; structured</option>
<option value="deep">Deep dive — technical</option>
</select><br><br>
<button type="submit" id="go">Explain</button>
</form>
<div id="result">Your explanation will appear here.</div>
<div class="meta" id="rmeta"></div>
<p><strong>API:</strong> <code>POST /api/explain {"topic","language","depth"}</code>
&middot; <code>GET /api/languages</code></p>
<footer>
<p>Polyglot Explainer — Hack Apertus Track 2B "Own Project".
Demo outputs are labeled <strong>[SIMULATED DEMO OUTPUT]</strong>; set
<code>LLM_API_KEY</code> for live Apertus explanations. Apache 2.0.</p>
</footer>
<script>
const LANGS = LANGS_JSON;
const chips = document.getElementById('chips');
let sel = 'en';
LANGS.forEach(l => {
  const s = document.createElement('span');
  s.className = 'chip' + (l.code === sel ? ' sel' : '');
  s.textContent = l.name;
  s.onclick = () => { sel = l.code;
    document.querySelectorAll('.chip').forEach(c => c.classList.remove('sel'));
    s.classList.add('sel'); };
  chips.appendChild(s);
});
document.getElementById('f').addEventListener('submit', async (e) => {
  e.preventDefault();
  const go = document.getElementById('go'), res = document.getElementById('result'),
        meta = document.getElementById('rmeta');
  go.disabled = true; res.textContent = 'Explaining…'; meta.textContent = '';
  try {
    const r = await fetch('/api/explain', {method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({topic: document.getElementById('topic').value,
                            language: sel,
                            depth: document.getElementById('depth').value})});
    const d = await r.json();
    if (!r.ok) { res.innerHTML = '<span class="err">Error: ' +
      (d.error || ('HTTP ' + r.status)) + '</span>'; return; }
    res.textContent = d.explanation;
    meta.textContent = 'model: ' + d.model + (d.demo ? ' (SIMULATED demo output)' : '') +
      (d.cached ? ' · served from cache' : '');
  } catch (err) { res.innerHTML = '<span class="err">Request failed: ' + err + '</span>'; }
  finally { go.disabled = false; }
});
</script>
</body></html>"""


@app.get("/")
def index():
    import json

    if DEMO_MODE:
        mode_class, mode_label = (
            "demo",
            "Demo mode — no LLM_API_KEY set; responses are simulated and labeled",
        )
    else:
        mode_class, mode_label = "live", f"Live mode — connected to {APERTUS_MODEL}"
    return _INDEX_HTML.replace("{mode_class}", mode_class).replace(
        "{mode_label}", mode_label
    ).replace("LANGS_JSON", json.dumps(LANGUAGES))


@app.get("/api/languages")
def languages():
    return jsonify({"languages": LANGUAGES, "count": len(LANGUAGES)})


@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok", "demo": DEMO_MODE, "model": APERTUS_MODEL})


def _validate_payload(payload: dict) -> tuple[dict | None, tuple[Any, int] | None]:
    topic = (payload.get("topic") or "").strip()
    language = (payload.get("language") or "en").strip()
    depth = (payload.get("depth") or "standard").strip()

    if not topic:
        return None, (jsonify({"error": "topic is required and must be non-empty"}), 400)
    if language not in {l["code"] for l in LANGUAGES}:
        return None, (jsonify({"error": f"unsupported language code: {language}"}), 400)
    if depth not in DEPTHS:
        return None, (
            jsonify({"error": f"unsupported depth: {depth}. Choose from {sorted(DEPTHS)}"}),
            400,
        )
    return {"topic": topic, "language": language, "depth": depth}, None


@app.post("/api/explain")
def explain() -> tuple[Any, int] | Any:
    payload = request.get_json(silent=True) or {}
    fields, error = _validate_payload(payload)
    if error:
        return error
    topic, language, depth = fields["topic"], fields["language"], fields["depth"]

    cache_key = (topic.lower(), language, depth)
    hit = _cache_get(cache_key)
    if hit is not None:
        explanation = hit
        cached = True
    else:
        cached = False
        if DEMO_MODE:
            explanation = _demo_explain(topic, language, depth)
        else:
            try:
                explanation = _live_explain(topic, language, depth)
            except requests.RequestException as exc:
                return (
                    jsonify({"error": f"upstream Apertus request failed: {exc}"}),
                    502,
                )
        _cache_put(cache_key, explanation)

    return jsonify({
        "topic": topic,
        "language": language,
        "depth": depth,
        "model": "demo" if DEMO_MODE else APERTUS_MODEL,
        "demo": DEMO_MODE,
        "cached": cached,
        "explanation": explanation,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
