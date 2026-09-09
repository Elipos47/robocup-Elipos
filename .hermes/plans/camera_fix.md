# Piano: fix orientamento camera verde + verifica headless (M1)

## Sintomi accertati (09/09/2026)
1. Rotazione `Camera` inefficace: Vhist bit-identico al variare di `rotation`
   (-0.785, -2.356, +0.785, ±1.5708) → la camera guarda sempre dritta
   all'orizzonte (conferma visiva utente su `cam_green.png`: pavimento + orizzonte).
2. "Crash" Webots in GUI dopo ~5s = `pose_probe` chiama `simulationQuit(0)`
   allo step 160. Non è un crash: rimuovere il blocco PROBE dal mondo.
3. Linea nera e landmark mai visibili nei frame → conseguenza di (1).

## Ipotesi da verificare (subagenti di ricerca)
- H1: asse ottico nativo / convenzione `rotation` diversa dal presunto
  (trovare valore esatto per avanti-basso 45° con marcia +Z, rif. e-puck).
- H2: rendering device disabilitato in `--batch --minimize` (frame stantii).

## Passi (in ordine)
1. [research] Subagente A: convenzione Camera Webots R2025a (asse nativo,
   semantica rotation, esempio e-puck) → valore `rotation` esatto.
2. [research] Subagente B: Camera headless in `--batch` (serve rendering?
   gotcha enable/timing?) → checklist frame validi.
3. [io] Rimuovere blocco `DEF PROBE` dal mondo (fix "crash"); tenere
   `pose_probe.py` come tool documentato in `docs/plans/verification_pipeline.md`.
4. [io] Applicare rotazione da (1); verifica: run headless + `saveImage`;
   conferma utente su PNG (linea nera centrata in basso al centro?).
5. [io] Rimuovere landmark LM_A/B/C + tutti i TEMP-DEBUG dal controller.
6. [io] Riattivare controllo visione (togliere dritto hardcoded), run probe:
   `|x|→0`, `dev→~0`; poi rimozioni finali, `pytest`, review indipendente, commit.
7. [io] Allineare SPEC §6.3/§7.1 (convenzione asse, threshold 60, luci flat).

## Criterio di chiusura
PNG utente mostra linea nera che attraversa il frame + run chiuso in anello
con |dev| < 40px su rettilineo.
