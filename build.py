#!/usr/bin/env python3
"""Build the Rafkraft static site from content/*.json."""

import argparse
import html
import json
import re
import shutil
import struct
from datetime import date
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent

MARK = (
    '<svg class="mark" viewBox="0 0 72 32" aria-hidden="true" focusable="false">'
    '<path d="M2 18H16l6-12 8 20 8-14 6 6h20" fill="none" stroke="currentColor" '
    'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


def esc(value):
    return html.escape(str(value), quote=True)


def clip(text, limit=160):
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0] + "…"


def e164(display):
    raw = re.sub(r"[^\d+]", "", display or "")
    if not raw:
        return ""
    if raw.startswith("00"):
        raw = "+" + raw[2:]
    if not raw.startswith("+"):
        raw = "+354" + raw
    return raw


def show_phone(display):
    return esc(display).replace(" ", "\u00a0")


def phone_link(display, class_name=""):
    number = e164(display)
    if not number:
        return ""
    cls = f' class="{class_name}"' if class_name else ""
    return f'<a{cls} href="tel:{esc(number)}">{show_phone(display)}</a>'


def call_button(site, class_name):
    return (
        f'<a class="{class_name}" href="tel:{esc(e164(site["phone"]))}">'
        f"Hringja · {show_phone(site['phone'])}</a>"
    )


def abs_url(site, rel):
    if rel.startswith(("http://", "https://")):
        return rel
    return site["site_url"].rstrip("/") + "/" + rel.lstrip("/")


def safe_href(url):
    if url.startswith(("#", "mailto:", "tel:")):
        return True
    if url.startswith(("http://", "https://")):
        return True
    if url.startswith(("javascript:", "data:", "//")):
        return False
    return ":" not in url.split("/", 1)[0]


def format_text(raw):
    safe = esc(raw)
    safe = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", safe)
    safe = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", safe)
    return safe


def inline(raw):
    pattern = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
    parts = []
    pos = 0
    for match in pattern.finditer(raw):
        parts.append(format_text(raw[pos : match.start()]))
        href = match.group(2)
        if safe_href(href):
            parts.append(f'<a href="{esc(href)}">{format_text(match.group(1))}</a>')
        else:
            parts.append(format_text(match.group(0)))
        pos = match.end()
    parts.append(format_text(raw[pos:]))
    return "".join(parts)


def md_to_html(src):
    lines = (src or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out = []
    paragraph = []
    items = []

    def flush_paragraph():
        nonlocal paragraph
        if paragraph:
            out.append("<p>" + inline(" ".join(paragraph)) + "</p>")
            paragraph = []

    def flush_items():
        nonlocal items
        if items:
            lis = "".join(f"<li>{inline(item)}</li>" for item in items)
            out.append(f"<ul>{lis}</ul>")
            items = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            flush_items()
            continue
        if stripped in ("---", "***"):
            flush_paragraph()
            flush_items()
            out.append("<hr>")
            continue
        heading = re.match(r"(#{1,6})\s+(.*)", stripped)
        if heading:
            flush_paragraph()
            flush_items()
            tag = "h2" if len(heading.group(1)) <= 2 else "h3"
            out.append(f"<{tag}>{inline(heading.group(2).strip())}</{tag}>")
            continue
        if stripped.startswith(("- ", "* ")):
            flush_paragraph()
            items.append(stripped[2:].strip())
            continue
        flush_items()
        paragraph.append(stripped)
    flush_paragraph()
    flush_items()
    return "\n".join(out)


def jpeg_size(path):
    data = path.read_bytes()
    if not data.startswith(b"\xff\xd8"):
        return None, None
    index = 2
    while index + 8 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            height, width = struct.unpack(">HH", data[index + 5 : index + 9])
            return width, height
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD9:
            index += 2
            continue
        if index + 4 > len(data):
            break
        length = struct.unpack(">H", data[index + 2 : index + 4])[0]
        index += 2 + length
    return None, None


def image_info(src):
    if src.startswith(("http://", "https://")):
        return src, None, None
    rel = src.lstrip("/")
    file = ROOT / rel
    if not file.is_file():
        raise SystemExit(f"Missing image: {rel}")
    width = height = None
    if file.suffix.lower() in {".jpg", ".jpeg"}:
        width, height = jpeg_size(file)
    return rel, width, height


def img_tag(src, alt, priority=False):
    rel, width, height = image_info(src)
    size = f' width="{width}" height="{height}"' if width and height else ""
    loading = ' fetchpriority="high"' if priority else ' loading="lazy"'
    return (
        f'<img src="{esc(rel)}" alt="{esc(alt)}"{size}{loading} decoding="async">'
    )


def figure(src, alt, caption="", wide=False, priority=False):
    kind = "frame frame-wide" if wide else "frame"
    cap = f"<figcaption>{esc(caption)}</figcaption>" if caption else ""
    return f"<figure><div class=\"{kind}\">{img_tag(src, alt, priority)}</div>{cap}</figure>"


def require(obj, key, where):
    if key not in obj or obj[key] in ("", None, []):
        raise SystemExit(f"Missing {key} in {where}")
    return obj[key]


def load():
    site_path = ROOT / "content" / "site.json"
    site = json.loads(site_path.read_text(encoding="utf-8"))
    for key in (
        "name",
        "legal_name",
        "tagline",
        "description",
        "site_url",
        "phone",
        "kennitala",
        "vsk_number",
        "founded",
        "founded_display",
        "isat",
        "address",
        "geo",
        "hero_kicker",
        "hero_title",
        "hero_text",
        "hero_image",
        "hero_image_alt",
        "about_image",
        "about_image_alt",
        "about_kicker",
        "about_title",
        "about_lead",
        "about_body",
        "services_kicker",
        "services_title",
        "services_lead",
        "steps_kicker",
        "steps_title",
        "steps_lead",
        "steps",
        "staff_kicker",
        "staff_title",
        "staff_lead",
        "contact_kicker",
        "contact_title",
        "contact_lead",
        "faq_title",
        "faq_lead",
        "faq",
    ):
        require(site, key, site_path)
    require(site["address"], "street", "address")
    require(site["address"], "postal_code", "address")
    require(site["address"], "city", "address")
    require(site["geo"], "lat", "geo")
    require(site["geo"], "lon", "geo")

    services = []
    for path in sorted((ROOT / "content" / "services").glob("*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        item["_slug"] = path.stem
        for key in ("title", "summary", "image", "image_alt", "body", "order"):
            require(item, key, path)
        services.append(item)
    services.sort(key=lambda item: (int(item["order"]), item["title"]))

    staff = []
    for path in sorted((ROOT / "content" / "staff").glob("*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        item["_slug"] = path.stem
        for key in ("name", "email", "order"):
            require(item, key, path)
        staff.append(item)
    staff.sort(key=lambda item: (int(item["order"]), item["name"]))
    if not services or not staff:
        raise SystemExit("Add at least one service and one staff member.")
    return site, services, staff


def initials(name):
    parts = [part.strip(".") for part in name.split() if part.strip(".")]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:1].upper()
    return (parts[0][:1] + parts[-1][:1]).upper()


def brand():
    return f'<a class="brand" href="index.html">{MARK}<span class="brand-name">Rafkraft</span></a>'


def header(site, active):
    items = [
        ("index.html", "Forsíða", "home"),
        ("thjonusta.html", "Þjónusta", "services"),
        ("um-okkur.html", "Um okkur", "about"),
        ("starfsfolk.html", "Starfsfólk", "staff"),
        ("samband.html", "Samband", "contact"),
    ]
    links = []
    for href, label, key in items:
        current = ' aria-current="page"' if key == active else ""
        links.append(f'<li><a href="{href}"{current}>{esc(label)}</a></li>')
    call = (
        f'<li class="nav-call"><a href="tel:{esc(e164(site["phone"]))}">Hringja</a></li>'
    )
    return f"""
<a class="skip" href="#efni">Fara í efni</a>
<header class="site-header">
  <div class="wrap header-inner">
    {brand()}
    <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav">
      <span class="bars" aria-hidden="true"></span>
      <span class="nav-toggle-label">Valmynd</span>
    </button>
    <nav id="site-nav" aria-label="Aðalvalmynd">
      <ul class="nav-list">
        {"".join(links)}
        {call}
      </ul>
    </nav>
  </div>
</header>
"""


def footer(site):
    address = site["address"]
    links = [
        ("index.html", "Forsíða"),
        ("thjonusta.html", "Þjónusta"),
        ("um-okkur.html", "Um okkur"),
        ("starfsfolk.html", "Starfsfólk"),
        ("samband.html", "Hafa samband"),
    ]
    nav = "".join(f'<li><a href="{href}">{esc(label)}</a></li>' for href, label in links)
    return f"""
<footer class="site-footer">
  <div class="wrap footer-grid">
    <div>
      {brand()}
      <p>{esc(site["tagline"])}.</p>
    </div>
    <div>
      <p class="footer-label">Sími og staður</p>
      <p>{phone_link(site["phone"])}<br>{esc(address["street"])}<br>{esc(address["postal_code"])} {esc(address["city"])}</p>
    </div>
    <nav aria-label="Fótvalmynd">
      <p class="footer-label">Síður</p>
      <ul class="footer-links">{nav}</ul>
    </nav>
  </div>
  <div class="wrap footer-base">
    <p>© {date.today().year} {esc(site["legal_name"])} · kt. {esc(site["kennitala"])} · VSK {esc(site["vsk_number"])}</p>
    <p>Vefurinn notar ekki vafrakökur.</p>
  </div>
</footer>
"""


def callbar(site):
    return (
        f'<a class="callbar" href="tel:{esc(e164(site["phone"]))}">'
        f"Hringja · {show_phone(site['phone'])}</a>"
    )


def crumbs(parts):
    bits = ['<nav class="crumbs" aria-label="Braut">']
    for index, (href, label) in enumerate(parts):
        if index:
            bits.append('<span class="sep" aria-hidden="true">/</span>')
        if href:
            bits.append(f'<a href="{href}">{esc(label)}</a>')
        else:
            bits.append(f'<span aria-current="page">{esc(label)}</span>')
    bits.append("</nav>")
    return "".join(bits)


def plate(site):
    address = site["address"]
    cells = [
        ("Stofnað", esc(site["founded_display"])),
        ("Kennitala", esc(site["kennitala"])),
        ("Sími", phone_link(site["phone"])),
        ("Starfsstöð", f'<a href="samband.html#kort">{esc(address["street"])}</a>'),
    ]
    html_cells = "".join(
        f'<div class="plate-item"><p class="plate-label">{esc(label)}</p>'
        f'<p class="plate-value">{value}</p></div>'
        for label, value in cells
    )
    return f'<section class="plate" aria-label="Lykiltölur">{html_cells}</section>'


def service_card(service):
    return f"""
<a class="card" href="{esc(service["_slug"])}.html">
  <div class="frame">{img_tag(service["image"], service["image_alt"])}</div>
  <div class="card-body">
    <h3>{esc(service["title"])}</h3>
    <p>{esc(service["summary"])}</p>
    <span class="more">Nánar</span>
  </div>
</a>
"""


def person_card(person):
    role = f'<p class="role">{esc(person["role"])}</p>' if person.get("role") else ""
    phone = f"<p>{phone_link(person['phone'])}</p>" if person.get("phone") else ""
    return f"""
<article class="person" id="{esc(person["_slug"])}">
  <div class="monogram" aria-hidden="true">{esc(initials(person["name"]))}</div>
  <div>
    <h2>{esc(person["name"])}</h2>
    {role}
    {phone}
    <p><a href="mailto:{esc(person["email"])}">{esc(person["email"])}</a></p>
  </div>
</article>
"""


def json_ld(site, services, staff):
    address = site["address"]
    people = []
    for person in staff:
        entry = {"@type": "Person", "name": person["name"], "email": person["email"]}
        if person.get("phone"):
            entry["telephone"] = e164(person["phone"])
        if person.get("role"):
            entry["jobTitle"] = person["role"]
        people.append(entry)
    data = {
        "@context": "https://schema.org",
        "@type": "Electrician",
        "name": site["legal_name"],
        "url": site["site_url"].rstrip("/") + "/",
        "image": abs_url(site, site["hero_image"]),
        "telephone": e164(site["phone"]),
        "foundingDate": site["founded"],
        "vatID": site["vsk_number"],
        "taxID": site["kennitala"],
        "address": {
            "@type": "PostalAddress",
            "streetAddress": address["street"],
            "postalCode": address["postal_code"],
            "addressLocality": address["city"],
            "addressCountry": "IS",
        },
        "geo": {
            "@type": "GeoCoordinates",
            "latitude": site["geo"]["lat"],
            "longitude": site["geo"]["lon"],
        },
        "employee": people,
        "hasOfferCatalog": {
            "@type": "OfferCatalog",
            "name": "Þjónusta",
            "itemListElement": [
                {
                    "@type": "Offer",
                    "itemOffered": {
                        "@type": "Service",
                        "name": service["title"],
                        "description": service["summary"],
                        "url": abs_url(site, service["_slug"] + ".html"),
                    },
                }
                for service in services
            ],
        },
    }
    if site.get("email"):
        data["email"] = site["email"]
    raw = json.dumps(data, ensure_ascii=False)
    return raw.replace("<", "\\u003c")


def document(site, services, staff, active, title, description, path, image, body, index=True, image_alt=None):
    full = (
        f"{site['legal_name']} · {site['tagline']}"
        if path == ""
        else f"{title} · {site['legal_name']}"
    )
    summary = clip(description)
    robots = "index,follow" if index else "noindex,nofollow"
    head = [
        "<!DOCTYPE html>",
        '<html lang="is">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{esc(full)}</title>",
        f'<meta name="description" content="{esc(summary)}">',
        '<meta name="theme-color" content="#12263f">',
        f'<meta name="robots" content="{robots}">',
        '<link rel="icon" href="assets/favicon.svg" type="image/svg+xml">',
        '<link rel="preconnect" href="https://fonts.googleapis.com">',
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        '<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Outfit:wght@500;600;700&family=Source+Sans+3:ital,wght@0,400;0,600;0,700;1,400&display=swap" rel="stylesheet">',
        '<link rel="stylesheet" href="css/styles.css">',
        '<script>document.documentElement.classList.add("js")</script>',
    ]
    if index:
        canonical = site["site_url"].rstrip("/") + ("/" if path == "" else "/" + path)
        og_image = abs_url(site, image or site["hero_image"])
        head.extend(
            [
                f'<link rel="canonical" href="{esc(canonical)}">',
                '<meta property="og:type" content="website">',
                '<meta property="og:locale" content="is_IS">',
                f'<meta property="og:site_name" content="{esc(site["legal_name"])}">',
                f'<meta property="og:title" content="{esc(full)}">',
                f'<meta property="og:description" content="{esc(summary)}">',
                f'<meta property="og:url" content="{esc(canonical)}">',
                f'<meta property="og:image" content="{esc(og_image)}">',
                f'<meta property="og:image:alt" content="{esc(image_alt or site["hero_image_alt"])}">',
                '<meta name="twitter:card" content="summary_large_image">',
            ]
        )
    head.append("</head>")
    ld = f'<script type="application/ld+json">{json_ld(site, services, staff)}</script>' if index else ""
    return f"""{chr(10).join(head)}
<body>
{header(site, active)}
<main id="efni">
{body}
</main>
{footer(site)}
{callbar(site)}
{ld}
<script src="js/site.js" defer></script>
</body>
</html>
"""


def home_page(site, services, staff):
    cards = "".join(service_card(service) for service in services)
    steps = "".join(
        f"""<article class="step"><p class="step-no">{index:02d}</p><h3>{esc(step["title"])}</h3><p>{esc(step["text"])}</p></article>"""
        for index, step in enumerate(site["steps"], 1)
    )
    names = "".join(
        f'<li><a href="starfsfolk.html#{esc(person["_slug"])}">{esc(person["name"])}</a></li>'
        for person in staff
    )
    body = f"""
<section class="hero">
  <div class="wrap hero-grid">
    <div>
      <p class="kicker">{esc(site["hero_kicker"])}</p>
      <h1>{esc(site["hero_title"])}</h1>
      <p class="lede">{esc(site["hero_text"])}</p>
      <div class="actions">
        {call_button(site, "btn btn-primary")}
        <a class="btn btn-secondary" href="thjonusta.html">Skoða þjónustu</a>
      </div>
    </div>
    {figure(site["hero_image"], site["hero_image_alt"], wide=True, priority=True)}
  </div>
</section>
<div class="wrap">{plate(site)}</div>
<section class="section" id="thjonusta">
  <div class="wrap">
    <div class="section-head">
      <p class="kicker">{esc(site["services_kicker"])}</p>
      <h2>{esc(site["services_title"])}</h2>
      <p class="lede">{esc(site["services_lead"])}</p>
    </div>
    <div class="cards">{cards}</div>
  </div>
</section>
<section class="section">
  <div class="wrap">
    <div class="section-head">
      <p class="kicker">{esc(site["steps_kicker"])}</p>
      <h2>{esc(site["steps_title"])}</h2>
      <p class="lede">{esc(site["steps_lead"])}</p>
    </div>
    <div class="steps">{steps}</div>
  </div>
</section>
<section class="section">
  <div class="wrap about-grid">
    <div>
      <p class="kicker">{esc(site["about_kicker"])}</p>
      <h2>{esc(site["about_title"])}</h2>
      <p class="lede">{esc(site["about_lead"])}</p>
      <div class="actions"><a class="btn btn-secondary" href="um-okkur.html">Um fyrirtækið</a></div>
    </div>
    {figure(site["about_image"], site["about_image_alt"], site.get("about_image_caption", ""), wide=True)}
  </div>
</section>
<section class="section">
  <div class="wrap">
    <div class="section-head">
      <p class="kicker">{esc(site["staff_kicker"])}</p>
      <h2>{esc(site["staff_title"])}</h2>
      <p class="lede">{esc(site["staff_lead"])}</p>
    </div>
    <ul class="name-list">{names}</ul>
  </div>
</section>
<section class="band">
  <div class="wrap">
    <p class="kicker">{esc(site["contact_kicker"])}</p>
    <h2>{esc(site["contact_title"])}</h2>
    <p class="lede">{esc(site["contact_lead"])}</p>
    <div class="actions">
      {call_button(site, "btn btn-primary")}
      <a class="btn btn-secondary" href="samband.html">Skrifa skilaboð</a>
    </div>
  </div>
</section>
"""
    return (
        "index.html",
        document(
            site,
            services,
            staff,
            "home",
            site["legal_name"],
            site["description"],
            "",
            site["hero_image"],
            body,
        ),
    )


def services_page(site, services, staff):
    cards = "".join(service_card(service) for service in services)
    body = f"""
<div class="wrap page-hero">
  {crumbs([("index.html", "Forsíða"), (None, "Þjónusta")])}
  <p class="kicker">{esc(site["services_kicker"])}</p>
  <h1>{esc(site["services_title"])}</h1>
  <p class="lede">{esc(site["services_lead"])}</p>
</div>
<section class="section">
  <div class="wrap cards">{cards}</div>
</section>
"""
    return (
        "thjonusta.html",
        document(
            site,
            services,
            staff,
            "services",
            "Þjónusta",
            site["services_lead"],
            "thjonusta.html",
            site["hero_image"],
            body,
        ),
    )


def service_page(site, service, services, staff):
    others = "".join(
        f'<li><a href="{esc(item["_slug"])}.html">{esc(item["title"])}</a></li>'
        for item in services
        if item["_slug"] != service["_slug"]
    )
    address = site["address"]
    body = f"""
<div class="wrap page-hero">
  {crumbs([("index.html", "Forsíða"), ("thjonusta.html", "Þjónusta"), (None, service["title"])])}
  <p class="kicker">{esc(site["services_kicker"])}</p>
  <h1>{esc(service["title"])}</h1>
  <p class="lede">{esc(service["summary"])}</p>
</div>
<div class="wrap section">
  {figure(service["image"], service["image_alt"], priority=True)}
  <div class="split">
    <div class="prose">{md_to_html(service["body"])}</div>
    <aside class="sidecard">
      <p class="kicker">Næsta skref</p>
      <p>Segðu okkur frá verkinu. Síminn er fljótastur.</p>
      <p class="sidecard-phone">{phone_link(site["phone"])}</p>
      <p>{esc(address["street"])}<br>{esc(address["postal_code"])} {esc(address["city"])}</p>
      <a class="btn btn-primary" href="samband.html">Senda fyrirspurn</a>
    </aside>
  </div>
  <h2>Önnur þjónusta</h2>
  <ul class="related">{others}</ul>
</div>
"""
    filename = service["_slug"] + ".html"
    return (
        filename,
        document(
            site,
            services,
            staff,
            "services",
            service["title"],
            service["summary"],
            filename,
            service["image"],
            body,
            image_alt=service["image_alt"],
        ),
    )


def about_page(site, services, staff):
    body = f"""
<div class="wrap page-hero">
  {crumbs([("index.html", "Forsíða"), (None, "Um okkur")])}
  <p class="kicker">{esc(site["about_kicker"])}</p>
  <h1>{esc(site["about_title"])}</h1>
  <p class="lede">{esc(site["about_lead"])}</p>
</div>
<section class="section">
  <div class="wrap split">
    <div class="prose">{md_to_html(site["about_body"])}</div>
    {figure(site["about_image"], site["about_image_alt"], site.get("about_image_caption", ""), wide=True, priority=True)}
  </div>
</section>
<div class="wrap">{plate(site)}</div>
<section class="section">
  <div class="wrap">
    <p class="lede">ÍSAT-flokkurinn er {esc(site["isat"])}. Starfsfólkið og bein símanúmer eru á sérsíðu.</p>
    <div class="actions">
      <a class="btn btn-secondary" href="starfsfolk.html">Starfsfólk</a>
      <a class="btn btn-primary" href="samband.html">Hafa samband</a>
    </div>
  </div>
</section>
"""
    return (
        "um-okkur.html",
        document(
            site,
            services,
            staff,
            "about",
            "Um okkur",
            site["about_lead"],
            "um-okkur.html",
            site["about_image"],
            body,
            image_alt=site["about_image_alt"],
        ),
    )


def staff_page(site, services, staff):
    cards = "".join(person_card(person) for person in staff)
    body = f"""
<div class="wrap page-hero">
  {crumbs([("index.html", "Forsíða"), (None, "Starfsfólk")])}
  <p class="kicker">{esc(site["staff_kicker"])}</p>
  <h1>{esc(site["staff_title"])}</h1>
  <p class="lede">{esc(site["staff_lead"])}</p>
  <p>Skrifstofa: {phone_link(site["phone"])}</p>
</div>
<section class="section">
  <div class="wrap people">{cards}</div>
</section>
"""
    return (
        "starfsfolk.html",
        document(
            site,
            services,
            staff,
            "staff",
            "Starfsfólk",
            site["staff_lead"],
            "starfsfolk.html",
            site["hero_image"],
            body,
        ),
    )


def contact_form(site, staff):
    options = ['<option value="">Veldu viðtakanda</option>']
    if site.get("email"):
        options.append(f'<option value="{esc(site["email"])}">Skrifstofa</option>')
    for person in staff:
        options.append(
            f'<option value="{esc(person["email"])}">{esc(person["name"])}</option>'
        )
    return f"""
<form id="fyrirspurn" action="#fyrirspurn" method="post">
  <div class="field">
    <label for="nafn">Nafn</label>
    <input id="nafn" name="name" autocomplete="name" required>
  </div>
  <div class="field">
    <label for="simi">Sími</label>
    <input id="simi" name="phone" type="tel" autocomplete="tel">
  </div>
  <div class="field">
    <label for="netfang">Netfang</label>
    <input id="netfang" name="email" type="email" autocomplete="email">
  </div>
  <div class="field">
    <label for="vidtakandi">Viðtakandi</label>
    <select id="vidtakandi" name="to" required>{"".join(options)}</select>
  </div>
  <div class="field">
    <label for="skilabod">Skilaboð</label>
    <textarea id="skilabod" name="message" required aria-describedby="skilabod-hint"></textarea>
    <p class="hint" id="skilabod-hint">Nefndu húsnæðið, hvað á að gera og hvenær þú vilt byrja.</p>
  </div>
  <button class="btn btn-primary" type="submit">Opna tölvupóst</button>
  <p class="form-note">Hnappurinn opnar tölvupóstforritið þitt með textanum tilbúnum. Vefurinn vistar ekkert.</p>
  <p id="form-status" role="status"></p>
</form>
"""


def map_block(site):
    lat = float(site["geo"]["lat"])
    lon = float(site["geo"]["lon"])
    address = site["address"]
    bbox = f"{lon - 0.012:.6f}%2C{lat - 0.006:.6f}%2C{lon + 0.012:.6f}%2C{lat + 0.006:.6f}"
    src = (
        "https://www.openstreetmap.org/export/embed.html?bbox="
        + bbox
        + f"&layer=mapnik&marker={lat:.7f}%2C{lon:.7f}"
    )
    osm = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=17/{lat}/{lon}"
    query = quote(f"{address['street']}, {address['postal_code']} {address['city']}")
    google = f"https://www.google.com/maps/search/?api=1&query={query}"
    title = f"Kort sem sýnir {address['street']} í {address['city']}"
    return f"""
<section class="section" id="kort">
  <div class="wrap">
    <div class="section-head">
      <h2>Kort</h2>
      <p class="lede">{esc(address["street"])}, {esc(address["postal_code"])} {esc(address["city"])}</p>
    </div>
    <div class="map-frame">
      <iframe title="{esc(title)}" src="{esc(src)}" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
    </div>
    <p class="map-links">
      <a href="{esc(osm)}" target="_blank" rel="noopener noreferrer">Opna í OpenStreetMap</a>
      <a href="{esc(google)}" target="_blank" rel="noopener noreferrer">Opna í Google Maps</a>
    </p>
  </div>
</section>
"""


def faq_block(site):
    items = "".join(
        f'<details class="faq-item"><summary>{esc(item["question"])}</summary><p>{esc(item["answer"])}</p></details>'
        for item in site["faq"]
    )
    return f"""
<section class="section" id="spurningar">
  <div class="narrow">
    <div class="section-head">
      <h2>{esc(site["faq_title"])}</h2>
      <p class="lede">{esc(site["faq_lead"])}</p>
    </div>
    {items}
  </div>
</section>
"""


def contact_page(site, services, staff):
    address = site["address"]
    hours = f"<p>{esc(site['hours'])}</p>" if site.get("hours") else ""
    people = []
    for person in staff:
        phone = f"<p>{phone_link(person['phone'])}</p>" if person.get("phone") else ""
        role = f'<p class="role">{esc(person["role"])}</p>' if person.get("role") else ""
        people.append(
            f"""<li><strong>{esc(person["name"])}</strong>{role}{phone}<p><a href="mailto:{esc(person["email"])}">{esc(person["email"])}</a></p></li>"""
        )
    body = f"""
<div class="wrap page-hero">
  {crumbs([("index.html", "Forsíða"), (None, "Hafa samband")])}
  <p class="kicker">{esc(site["contact_kicker"])}</p>
  <h1>{esc(site["contact_title"])}</h1>
  <p class="lede">{esc(site["contact_lead"])}</p>
</div>
<section class="section">
  <div class="wrap contact-grid">
    <div>
      {phone_link(site["phone"], "contact-phone")}
      <p>{esc(address["street"])}<br>{esc(address["postal_code"])} {esc(address["city"])}</p>
      {hours}
      <p>Kennitala {esc(site["kennitala"])}<br>VSK {esc(site["vsk_number"])}</p>
      <ul class="contact-list">{"".join(people)}</ul>
    </div>
    <div class="panel form-panel">
      <noscript><p>Tölvupósturinn hér opnast með skriftu. Netföngin eru í listanum til hliðar.</p></noscript>
      {contact_form(site, staff)}
    </div>
  </div>
</section>
{map_block(site)}
{faq_block(site)}
"""
    return (
        "samband.html",
        document(
            site,
            services,
            staff,
            "contact",
            "Hafa samband",
            site["contact_lead"],
            "samband.html",
            site["hero_image"],
            body,
        ),
    )


def missing_page(site, services, staff):
    body = """
<div class="wrap page-hero missing">
  <p class="kicker">404</p>
  <h1>Síðan fannst ekki</h1>
  <p class="lede">Slóðin er ekki til. Forsíðan og þjónustusíðurnar eru hér fyrir neðan.</p>
  <div class="actions">
    <a class="btn btn-primary" href="index.html">Forsíða</a>
    <a class="btn btn-secondary" href="thjonusta.html">Þjónusta</a>
  </div>
</div>
"""
    return (
        "404.html",
        document(
            site,
            services,
            staff,
            "",
            "Síða fannst ekki",
            "Síðan fannst ekki á vef Rafkraft.",
            "404.html",
            site["hero_image"],
            body,
            index=False,
        ),
    )


def sitemap(site, names):
    base = site["site_url"].rstrip("/")
    today = date.today().isoformat()
    urls = []
    for name in names:
        if name == "404.html":
            continue
        loc = base + "/" if name == "index.html" else f"{base}/{name}"
        urls.append(f"  <url><loc>{esc(loc)}</loc><lastmod>{today}</lastmod></url>")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )


def robots_txt(site):
    base = site["site_url"].rstrip("/")
    return f"User-agent: *\nAllow: /\nDisallow: /admin/\n\nSitemap: {base}/sitemap.xml\n"


def check_links(out, pages):
    files = [out / name for name, _ in pages]
    admin = out / "admin" / "index.html"
    if admin.is_file():
        files.append(admin)
    missing = []
    for page in files:
        text = page.read_text(encoding="utf-8")
        for url in re.findall(r'(?:href|src)="([^"]+)"', text):
            if url.startswith(("http://", "https://", "mailto:", "tel:", "#", "data:")):
                continue
            target = (page.parent / url.split("#", 1)[0]).resolve()
            if url.split("#", 1)[0] and not target.is_file():
                missing.append(f"{page.name} -> {url}")
    if missing:
        raise SystemExit("Broken links:\n" + "\n".join(missing))


def build_pages(site, services, staff):
    pages = [
        home_page(site, services, staff),
        services_page(site, services, staff),
        about_page(site, services, staff),
        staff_page(site, services, staff),
        contact_page(site, services, staff),
    ]
    pages.extend(service_page(site, service, services, staff) for service in services)
    pages.append(missing_page(site, services, staff))
    return pages


def main():
    parser = argparse.ArgumentParser(description="Build the Rafkraft static site.")
    parser.add_argument(
        "--out",
        default=".",
        help="Output directory inside the project. '.' writes the site to the repo root.",
    )
    args = parser.parse_args()
    out = (ROOT / args.out).resolve()
    if out != ROOT and ROOT not in out.parents:
        raise SystemExit("Output must stay inside the project folder.")
    site, services, staff = load()
    if out == ROOT:
        for path in ROOT.glob("*.html"):
            path.unlink()
    else:
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        for name in ("assets", "css", "js", "admin"):
            shutil.copytree(ROOT / name, out / name)
    pages = build_pages(site, services, staff)
    for name, markup in pages:
        (out / name).write_text(markup, encoding="utf-8")
    names = [name for name, _ in pages]
    (out / "sitemap.xml").write_text(sitemap(site, names), encoding="utf-8")
    (out / "robots.txt").write_text(robots_txt(site), encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    check_links(out, pages)
    print(f"Built {len(pages)} pages in {out}")


if __name__ == "__main__":
    main()
