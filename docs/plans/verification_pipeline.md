# Pipeline di verifica (sim + fisico)

Obiettivo: ogni problema arriva all'agente in forma **riproducibile**,
ogni fix riparte da lì. Niente "non funziona" senza contesto.

## 1. Formato segnalazione (vale per Webots e robot fisico)

```text
DOVE:    sim (nome scenario .json + .wbt) | fisico (quale pista, luce)
COSA:    comportamento atteso vs osservato (2 righe max)
PROVE:   log JSONL (docs/logs/) + video/screen della run
CODICE:  branch + commit testato
```

Senza log + scenario la segnalazione torna al mittente.

## 2. Loop simulazione (Webots)

```text
tu definisci sintomo → agente scrive fix + test in src/tests/
→ pytest src/tests -q verde → tu esegui scenario in Webots
→ log JSONL + metriche (collect_metrics.py) + report (generate_report.py)
→ APPROVA (merge) o RICHIEDI MODIFICHE (nuovo ciclo con stesso formato)
```

- Scenari in `simulation/scenarios/*.json`, uno per situazione di gara:
  `basic_straight`, `curve_90`, `incroci`, `verde_dx_sx`, `ostacolo`,
  `stanza_vittime`, `uturn`, `rampa`, `luce_variabile`.
- Ogni scenario ha **criteri di accettazione** (es. 10/10 run, deviazione < 2cm).
- I parametri si tunano solo in sim, mai al buio sul fisico (§3.2 SPEC).

## 3. Loop robot fisico

Checklist pre-run (sempre, 2 minuti):

- [ ] Batteria carica (V misurata) — collegamenti § mappa in `hardware_reale.md`
- [ ] Cingoli tesi, camere pulite e fissate (angoli: verde 45°, nera frontale)
- [ ] Luci Pi accese se luce ambiente scarsa
- [ ] Stesso commit testato in sim (niente codice "al volo" non passato in sim)

Report fisico = stesso formato §1 + foto/video + V batteria + luce ambiente.
Se il fisico fallisce dove la sim passa → si aggiunge uno scenario sim
che replica il caso (es. `luce_variabile`, attrito diverso), poi fix lì.

## 4. Tassonomia fallimenti (per il target 99%)

- **Bug di codice** (non ammessi a regime): crash, stati morti FSM,
  threshold hardcoded, eccezioni non gestite, YOLO/latenza fuori budget.
- **Esterni** (gli unici ammessi): luce accecante/buio, pista sporca/danneggiata,
  batteria scarica, fili staccati, cingoli che slittano su sporco, regolamento nuovo.
- Ogni run fallita viene classificata così nel report. Il 99% si misura
  sui bug di codice = 0 su 100 run nominali; gli esterni si contano a parte
  e generano contromisure (es. check batteria obbligatorio).
