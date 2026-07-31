# Darba pierādījumi / Work Evidence

Bug-triage LangGraph projekts — vizuāls pierādījumu komplekts onsite vērtētājam.

**Projekts:** `c:\Users\Agnis\Desktop\langpath`  
**Datums:** 2026-07-31  
**Kā reproducēt:** `docker compose up -d` → skatīt tabulu zemāk

---

## Indekss

| # | Fails | Ko pierāda / What it proves |
|---|-------|-----------------------------|
| 1 | [01-docker-ps.png](01-docker-ps.png) | Docker Compose: 3 konteineri (`gitea`, `postgres`, `triage-service`) ar statusu **healthy** |
| 2 | [02-health.png](02-health.png) | `GET http://localhost:8000/health` → `{"status":"healthy","service":"bug-triage","version":"1.0.0"}` |
| 3 | [03-gitea-issues.png](03-gitea-issues.png) | Gitea repozitorija issues saraksts — Set A issues **#1–#4** (login, CSV export, password reset, dashboard charts). Papildus #18 no live API demo. |
| 4 | [04-gitea-pr16.png](04-gitea-pr16.png) | Gitea PR **#16** — kandidāta iesniegums vērtētājam (`candidate/langpath-implementation` → `main`) |
| 5 | [05-gitea-issue-exist1.png](05-gitea-issue-exist1.png) | Set A issue **EXIST-1** (#1): “Login button unresponsive on mobile Safari” + automātiski duplicate komentāri |
| 6a | [06-github-merged-prs-browser.png](06-github-merged-prs-browser.png) | GitHub merged PRs — **#9, #10, #11** redzami pārlūkā (repo: `IWill29/bug-triage-langgraph`) |
| 6b | [06-github-prs.png](06-github-prs.png) | GitHub merged PRs — `gh pr list --state merged` (CLI alternatīva) |
| 7 | [07-pytest.png](07-pytest.png) | `python -m pytest tests/ -q` → **50 passed** |
| 8 | [08-set-b.png](08-set-b.png) | `python scripts/run_set_b.py` → **8/8** (mocked Set B) |
| 9 | [09-live-b5.png](09-live-b5.png) | *(Opcionāli)* Live `B5_duplicate` — duplicate atpazīšana pret EXIST-1, komentārs Gitea #1 |
| 10 | [10-api-triage.png](10-api-triage.png) | `POST /api/triage` ar B1 paraugu → JSON atbilde (`status: created`, severity, components) |

---

## Papildu teksta izvades (bez attēla)

| Fails | Saturs |
|-------|--------|
| `01-docker-ps-output.txt` | Pilns `docker compose ps` raw output |
| `07-pytest-output.txt` | Pilns pytest izvade |
| `08-set-b-output.txt` | Pilns Set B mocked izvade ar node logiem |
| `09-live-b5-output.txt` | Pilns live B5 izvade |
| `10-api-triage-output.txt` | Pilna API JSON atbilde |

---

## Infrastruktūra

```
docker compose ps
curl http://localhost:8000/health
```

Visi servisi darbojas uz:
- Gitea: http://localhost:3000
- Triage API: http://localhost:8000
- Postgres: localhost:5432

---

## Piezīmes vērtētājam

1. **Set A issues (#1–4):** Seed skripts `scripts/seed_gitea.py`. Issues #1–#4 atbilst brief Set A (EXIST-1 … EXIST-4).
2. **Issue #18:** Radās live `POST /api/triage` demo laikā (B1 paraugs) — pierāda, ka API reāli izveido Gitea issue.
3. **GitHub:** Pārlūks sasniedza publisko repo bez login; PR #9–#11 redzami. CLI verifikācija: `gh pr list --repo IWill29/bug-triage-langgraph --state merged`.
4. **Drošība:** Screenshotos nav API atslēgu, tokeni vai `.env` satura.
5. **Live B5:** Veiksmīgs ar OpenAI + lokālo Gitea; duplicate komentārs pievienots issue #1.

---

## Ātrā verifikācija

```powershell
cd c:\Users\Agnis\Desktop\langpath
docker compose ps
python -m pytest tests/ -q
python scripts/run_set_b.py
python scripts/run_set_b.py --live --sample B5_duplicate
```

---

*Ģenerēts automatizēti darba pierādījumu pakotnei.*
