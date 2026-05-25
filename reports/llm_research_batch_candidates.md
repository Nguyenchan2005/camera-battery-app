# LLM-Assisted Manual Research Batch

Generated: 2026-05-25
Mode: apply

The agent researches sources outside this script. The script only validates recorded evidence and applies source-backed decisions; it never invents a battery mapping.

## Summary

| Metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| verified_cameras | 1006 | 1006 | 0 |
| unresolved_models | 987 | 987 | 0 |
| compatibility_rows | 1463 | 1463 | 0 |
| batteries | 130 | 130 | 0 |
| candidates | 1993 | 1993 | 0 |
| suggestions | 1 | 1 | 0 |

- Priority tasks selected: 100
- Evidence records reviewed in selected batch: 1
- Promoted in this run: 0
- Suggestions added in this run: 0

## Research Decisions

| Camera | Current/apply status | Proposed battery | Evidence level | Source | Source text | Decision | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Panasonic Lumix DMC-ZS50 | already_verified | DMW-BCM13PP | verified_high | official_manual: https://help.panasonic.ca/viewing/ALL/DMC-ZS50PC/OI/sqt0613-eng/sqt0613-eng.pdf | Panasonic DMC-ZS50 / DMC-TZ70 Basic Owner's Manual: The battery that can be used with this unit is DMW-BCM13PP. | promote_verified | verified_high source satisfies promotion policy. |

## Initial Test Cases

| Query | Camera ID | Resulting battery ID | Decision | Reason |
| --- | --- | --- | --- | --- |
| Samsung WB1000 | samsung_wb1000 | samsung_slb_11a | already_verified | Verified mapping already existed before this research batch. |
| Samsung TL320 | samsung_wb1000 | samsung_slb_11a | already_verified | Verified mapping already existed before this research batch. |
| Sony DSC-RX10 | sony_cyber_shot_dsc_rx10 | sony_np_fw50 | already_verified | Verified mapping already existed before this research batch. |
| Sony DSC-HX30V | sony_cyber_shot_dsc_hx30v | sony_np_bg1, sony_np_fg1 | already_verified | Verified mapping already existed before this research batch. |
| Sony DSC-W530 | sony_cyber_shot_dsc_w530 | sony_np_bn1 | already_verified | Verified mapping already existed before this research batch. |
| Fujifilm FinePix F31fd | fujifilm_finepix_f31fd | fujifilm_np_95 | already_verified | Verified mapping already existed before this research batch. |
| Panasonic TZ70 / ZS50 | panasonic_lumix_dmc_zs50 | panasonic_dmw_bcm13, panasonic_dmw_bcm13pp | already_verified | verified_high source satisfies promotion policy. |
| Nikon Coolpix S9500 | nikon_coolpix_s9500 | nikon_en_el12 | already_verified | Verified mapping already existed before this research batch. |
| Casio Exilim EX-ZR1000 | casio_exilim_ex_zr1000 | casio_np_130 | already_verified | Verified mapping already existed before this research batch. |
| Kodak EasyShare C613 | kodak_easyshare_c613 | generic_aa | already_verified | Verified mapping already existed before this research batch. |

## Alias Corrections

- Removed conflicting ZS50 alias from panasonic_lumix_dmc_tz50; Panasonic manual associates ZS50 with TZ70.

## Selected Tasks Still Awaiting Evidence

| Camera | Brand | Search queries prepared | Reason |
| --- | --- | ---: | --- |
| Sony Cyber-shot DSC-T25 | Sony | 15 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Nikon COOLPIX P100 | Nikon | 14 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Fujifilm FinePix F20 | Fujifilm | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Panasonic Lumix DC-FZ80D | Panasonic | 12 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Olympus Stylus 400 | Olympus | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Samsung ST100 | Samsung | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Casio Exilim EX-ZR10 | Casio | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Kodak EasyShare C1013 | Kodak | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Pentax Optio 230 | Pentax | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Ricoh Caplio RX | Ricoh | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| HP PhotoSmart 120 | HP | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| MINOLTA DiMAGE G400 | Minolta | 12 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Konica Minolta DiMAGE A2 | Konica Minolta | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Leica C-Lux | Leica | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Sigma DP0 | Sigma | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Sony Cyber-shot DSC-T66 | Sony | 15 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Nikon COOLPIX P3 | Nikon | 14 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Fujifilm FinePix F401 | Fujifilm | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Panasonic Lumix DC-LX100 II | Panasonic | 12 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Olympus Stylus 500 | Olympus | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Samsung ST30 | Samsung | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Casio Exilim EX-ZR15 | Casio | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Kodak EasyShare C122 | Kodak | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Pentax Optio 30 | Pentax | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Ricoh CX1 | Ricoh | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| HP PhotoSmart 210 | HP | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| MINOLTA DiMAGE G500 | Minolta | 12 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Konica Minolta DiMAGE A200 | Konica Minolta | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Leica C-Lux 1 | Leica | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Sigma DP1 | Sigma | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Sony Cyber-shot DSC-T75 | Sony | 15 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Nikon COOLPIX P4 | Nikon | 14 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Fujifilm FinePix F470 | Fujifilm | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Panasonic Lumix DC-ZS99 | Panasonic | 12 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Olympus C-150 | Olympus | 10 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Samsung ST500 | Samsung | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Casio Exilim EX-ZR2100 | Casio | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Kodak EasyShare C123 | Kodak | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Pentax Optio 330 | Pentax | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Ricoh CX2 | Ricoh | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| HP PhotoSmart 215 | HP | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Minolta DiMAGE E201 | Minolta | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Konica Minolta DiMAGE E40 | Konica Minolta | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Leica C-Lux 2 | Leica | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Sigma DP1m | Sigma | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Sony Cyber-shot DSC-TX77 | Sony | 15 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Nikon COOLPIX P50 | Nikon | 14 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Fujifilm FinePix F480 | Fujifilm | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Panasonic Lumix DMC-FZ1000II | Panasonic | 12 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Olympus C-160 | Olympus | 10 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Samsung ST5000 | Samsung | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Casio Exilim EX-ZR3000 | Casio | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Kodak EasyShare C142 | Kodak | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Pentax Optio 33LF | Pentax | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Ricoh CX3 | Ricoh | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| HP PhotoSmart 315 | HP | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Minolta DiMAGE E203 | Minolta | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Konica Minolta DiMAGE E50 | Konica Minolta | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Leica C-Lux 3 | Leica | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Sigma DP1s | Sigma | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Sony Cyber-shot DSC-WX9 | Sony | 15 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Nikon COOLPIX P5000 | Nikon | 14 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Fujifilm FinePix F601 Zoom | Fujifilm | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Panasonic Lumix DMC-FZ2000 | Panasonic | 12 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Olympus C-170 | Olympus | 10 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Samsung ST550 | Samsung | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Casio Exilim EX-ZR3500 | Casio | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Kodak EasyShare C143 | Kodak | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Pentax Optio 430 | Pentax | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Ricoh CX4 | Ricoh | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| HP PhotoSmart 318 | HP | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Minolta DiMAGE E223 | Minolta | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Konica Minolta DiMAGE E500 | Konica Minolta | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Leica D-Lux | Leica | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Sigma DP2 | Sigma | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Sony Cyber-shot DSC-H100 | Sony | 15 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Nikon COOLPIX P530 | Nikon | 14 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Fujifilm FinePix A101 | Fujifilm | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Panasonic Lumix DMC-FZ38 | Panasonic | 12 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Olympus C-180 | Olympus | 10 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Samsung ST5500 | Samsung | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Casio Exilim EX-ZR3600 | Casio | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Kodak EasyShare C1450 | Kodak | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Pentax Optio 43WR | Pentax | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Ricoh CX5 | Ricoh | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| HP PhotoSmart 320 | HP | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Minolta DiMAGE E323 | Minolta | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Konica Minolta DiMAGE G530 | Konica Minolta | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Leica D-Lux 2 | Leica | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Sigma DP2m | Sigma | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Sony Cyber-shot DSC-H20 | Sony | 15 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Nikon COOLPIX P60 | Nikon | 14 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Fujifilm FinePix A120 | Fujifilm | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Panasonic Lumix DMC-TZ50 | Panasonic | 12 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Olympus C-310 | Olympus | 10 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Samsung ST600 | Samsung | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Casio Exilim EX-ZR50 | Casio | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Kodak EasyShare C15 | Kodak | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Pentax Optio 450 | Pentax | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |

## Twenty Popular Models Still Unresolved

| Camera | Brand | Current reason |
| --- | --- | --- |
| Sony Cyber-shot DSC-T25 | Sony | Camera existence confirmed, battery not yet source-verified |
| Sony Cyber-shot DSC-T66 | Sony | Camera existence confirmed, battery not yet source-verified |
| Sony Cyber-shot DSC-T75 | Sony | Camera existence confirmed, battery not yet source-verified |
| Sony Cyber-shot DSC-TX77 | Sony | Camera existence confirmed, battery not yet source-verified |
| Sony Cyber-shot DSC-WX9 | Sony | Camera existence confirmed, battery not yet source-verified |
| Nikon COOLPIX P100 | Nikon | Checked source but no explicit battery/power mapping was extracted. |
| Nikon COOLPIX P3 | Nikon | Checked source but no explicit battery/power mapping was extracted. |
| Nikon COOLPIX P4 | Nikon | Checked source but no explicit battery/power mapping was extracted. |
| Nikon COOLPIX P50 | Nikon | Checked source but exact model match was not confirmed. |
| Nikon COOLPIX P5000 | Nikon | Checked source but no explicit battery/power mapping was extracted. |
| Nikon COOLPIX P530 | Nikon | Checked source but exact model match was not confirmed. |
| Nikon COOLPIX P60 | Nikon | Checked source but exact model match was not confirmed. |
| Nikon COOLPIX P80 | Nikon | Checked source but exact model match was not confirmed. |
| Nikon COOLPIX P90 | Nikon | Checked source but exact model match was not confirmed. |
| Nikon COOLPIX S02 | Nikon | Checked source but no explicit battery/power mapping was extracted. |
| Nikon COOLPIX S10 | Nikon | Checked source but no explicit battery/power mapping was extracted. |
| Nikon COOLPIX S2 | Nikon | Checked source but no explicit battery/power mapping was extracted. |
| Nikon COOLPIX S200 | Nikon | Checked source but exact model match was not confirmed. |
| Nikon COOLPIX S210 | Nikon | Checked source but exact model match was not confirmed. |
| Nikon COOLPIX S220 | Nikon | Checked source but exact model match was not confirmed. |
