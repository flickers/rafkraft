# Rafkraft

Static Icelandic website for Rafkraft ehf., an electrical contractor at Bíldshöfði 14 in Reykjavík. The pages are generated from JSON so the same files can be edited in [Decap CMS](https://decapcms.org/) and published with GitHub Pages.

## Preview

```bash
python3 build.py
python3 -m http.server 8080
```

Open http://localhost:8080. `build.py` reads `content/` and writes the HTML into the project root. It uses only the Python standard library.

## Edit the text

Content lives in:

- `content/site.json` — company facts, homepage copy, steps, and questions
- `content/services/` — one JSON file per service
- `content/staff/` — one JSON file per person

After a content change, run `python3 build.py` again. Do not hand-edit the HTML; the next build replaces it.

### On your computer

In one terminal, serve the site at `localhost` (Decap ignores the local backend on other hostnames):

```bash
python3 -m http.server 8080
```

In another:

```bash
npx decap-server
```

Open http://localhost:8080/admin/, choose the local backend, and save. Then rebuild.

### On the published site

Decap’s GitHub backend cannot log in from a purely static host. GitHub requires an OAuth server.

1. In `admin/config.yml`, set `repo` to `your-user/rafkraft` and keep `branch` aligned with the default branch.
2. Add an OAuth provider from the [Decap external OAuth clients](https://decapcms.org/docs/external-oauth-clients/) list, then set `base_url` and `auth_endpoint` in `admin/config.yml`.
3. Give editors write access to the repository.

People who only need to draft copy can keep using the local backend and push the JSON themselves.

The CMS interface is English. The field labels are Icelandic. Decap CMS 3.16.3 is vendored in `admin/` under the MIT license (`admin/DECAP-LICENSE.txt`).

## Publish on GitHub Pages

1. Push the repository to GitHub.
2. In the repository settings, open Pages and set the source to **GitHub Actions**.
3. The workflow `.github/workflows/pages.yml` runs `build.py` and deploys the result.

A push that only changes JSON still updates the live site, because the action rebuilds the HTML. The HTML already in the repository is the review copy.

For a project site such as `https://user.github.io/rafkraft/`, relative links work as they are. Set `site_url` in `content/site.json` to the address you actually publish, so the canonical URL and sitemap match it.

### Custom domain

When DNS for rafkraft.is should point here, add a `CNAME` file containing `rafkraft.is` and set that domain in the Pages settings. Leave the file out until the new site is the one you want the domain to serve.

## What came from the current site

Kept from [rafkraft.is](https://rafkraft.is/) and the company register at Skatturinn:

- Rafkraft ehf., kennitala 430377-0199, registered 3 March 1977
- VSK number 23326, ÍSAT 43.21.0 Raflagnir
- Bíldshöfði 14, 110 Reykjavík, phone 567 4911
- The four services on the old site: nýlagnir, endurnýjun raflagna, raflagnaþjónusta, raflagnateikningar
- Axel Darri Guðmundsson, Sigurður K. Guðnason, Guðjón Gunnar Ögmundsson (meistari), and Ögmundur Guðmundsson, with the phone numbers and emails published on the old site

Hleðslustöðvar, iðnaðarvélar, lýsing, brunaviðvörun and tölvu- og fjarskiptalagnir were added because those jobs are commonly offered by other Icelandic electrical contractors. They are written as work Rafkraft can take on, not as a claim copied from the old website.

The service descriptions, the short process, and the questions are new copy written around those services. The site does not claim a 24-hour rota, a price list, named customers, or a licence class that was not on the old site.

The photographs are illustrations made for this redesign. They are not pictures of Rafkraft’s jobs or of the premises. Replace them in Decap, and clear the caption on the about image if you upload a real photo of Bíldshöfði 14.
