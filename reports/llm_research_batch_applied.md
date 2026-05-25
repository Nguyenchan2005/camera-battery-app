# LLM-Assisted Manual Research Batch

Generated: 2026-05-25
Mode: apply

The agent researches sources outside this script. The script only validates recorded evidence and applies source-backed decisions; it never invents a battery mapping.

## Summary

| Metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| verified_cameras | 601 | 614 | 13 |
| unresolved_models | 1222 | 1210 | -12 |
| compatibility_rows | 778 | 791 | 13 |
| batteries | 93 | 96 | 3 |
| candidates | 1823 | 1824 | 1 |
| suggestions | 1 | 1 | 0 |

- Priority tasks selected: 50
- Evidence records reviewed in selected batch: 13
- Promoted in this run: 13
- Suggestions added in this run: 0

## Research Decisions

| Camera | Current/apply status | Proposed battery | Evidence level | Source | Source text | Decision | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Samsung WB1000 | applied | SLB-11A | verified_medium | manual_mirror: https://manualzz.com/doc/49237037/samsung-wb1000-user-manual | Samsung WB1000 User Manual: Power source - Rechargeable battery: Lithium-ion battery (SLB-11A, 1,130 mAh). Battery specifications: Mode SLB-11A, Type Lithium-ion battery, Cell capacity 1,130 mAh, Voltage 3.8 V. | promote_verified | verified_medium source satisfies promotion policy. |
| Sony Cyber-shot DSC-RX10 | applied | NP-FW50 | verified_high | official_manual: https://www.sony.com/electronics/support/compact-cameras-dsc-rx-series/dsc-rx10/specifications | Sony DSC-RX10 Specifications: Supplied Battery - Rechargeable Battery Pack NP-FW50. | promote_verified | verified_high source satisfies promotion policy. |
| Sony Cyber-shot DSC-HX30V | applied | NP-BG1 | verified_high | official_manual: https://www.sony-asia.com/electronics/support/compact-cameras-dsc-hx-series/dsc-hx30v/specifications | Sony DSC-HX30V Specifications: Rechargeable Battery Pack NP-BG1. | promote_verified | verified_high source satisfies promotion policy. |
| Sony Cyber-shot DSC-W530 | applied | NP-BN1 | verified_high | official_manual: https://www.sony.jp/cyber-shot/products/archive/DSC-W530/spec.html | Sony DSC-W530 official specifications: Battery system NP-BN1; supplied accessory Rechargeable Battery Pack NP-BN1. | promote_verified | verified_high source satisfies promotion policy. |
| Panasonic Lumix DMC-ZS50 | applied | DMW-BCM13PP | verified_high | official_manual: https://help.panasonic.ca/viewing/ALL/DMC-ZS50PC/OI/sqt0613-eng/sqt0613-eng.pdf | Panasonic DMC-ZS50 / DMC-TZ70 Basic Owner's Manual: The battery that can be used with this unit is DMW-BCM13PP. | promote_verified | verified_high source satisfies promotion policy. |
| Kodak EasyShare C613 | applied | AA | verified_medium | manual_mirror: https://www.manualslib.com/manual/89231/Kodak-Easyshare-C613.html | Kodak EasyShare C613 User Manual: Power - (2) Kodak oxy-alkaline digital camera batteries AA; (2) Kodak Ni-MH rechargeable digital camera batteries AA; Kodak Ni-MH rechargeable digital camera battery KAA2HR. | promote_verified | verified_medium source satisfies promotion policy. |
| Sony Cyber-shot DSC-W570 | applied | NP-BN1 | verified_high | official_manual: https://www.sony.jp/cyber-shot/products/archive/DSC-W570/spec.html | Sony DSC-W570 official specifications: Battery system NP-BN1; supplied accessory Rechargeable Battery Pack NP-BN1. | promote_verified | verified_high source satisfies promotion policy. |
| Sony Cyber-shot DSC-HX200V | applied | NP-FH50 | verified_high | official_manual: https://www.sony.fr/electronics/support/compact-cameras-dsc-hx-series/dsc-hx200v/specifications | Sony DSC-HX200V official specifications: Supplied rechargeable battery NP-FH50. | promote_verified | verified_high source satisfies promotion policy. |
| Sony Cyber-shot DSC-H90 | applied | NP-BG1 | verified_high | official_manual: https://www.sony.es/electronics/support/compact-cameras-dsc-h-series/dsc-h90/specifications | Sony DSC-H90 official specifications: Supplied battery NP-BG1. | promote_verified | verified_high source satisfies promotion policy. |
| Sony Cyber-shot DSC-HX20V | applied | NP-BG1 | verified_high | official_manual: https://www.sony-asia.com/electronics/support/compact-cameras-dsc-hx-series/dsc-hx20v/downloads/Y0014762 | Sony firmware instructions for DSC-HX20V: Things to be prepared - Fully charged rechargeable battery pack NP-BG1 (supplied). | promote_verified | verified_high source satisfies promotion policy. |
| Sony Cyber-shot DSC-HX10V | applied | NP-BG1 | verified_high | official_manual: https://www.sony-asia.com/electronics/support/compact-cameras-dsc-hx-series/dsc-hx10v/specifications | Sony DSC-HX10V official specifications: Rechargeable Battery Pack NP-BG1. | promote_verified | verified_high source satisfies promotion policy. |
| Sony Cyber-shot DSC-H70 | applied | NP-BG1 | verified_high | official_manual: https://www.sony-asia.com/corporate/resources/en_AP/pdf/specsheet_CES2011Cyber-shot_CCD.pdf | Sony official specification sheet: DSC-H70 supplied accessories include Rechargeable Battery Pack NP-BG1. | promote_verified | verified_high source satisfies promotion policy. |
| Sony Cyber-shot DSC-H55 | applied | NP-BG1 | verified_high | official_manual: https://www.sony-asia.com/corporate/resources/en_AP/pdf/Specification_Sheet_for_DSC-TX5_and_DSC-H55.pdf | Sony official DSC-H55 specification sheet: Battery / AC adaptor - NP-BG1 3.6 V / AC-LS5 4.2 V. | promote_verified | verified_high source satisfies promotion policy. |

## Initial Test Cases

| Query | Camera ID | Resulting battery ID | Decision | Reason |
| --- | --- | --- | --- | --- |
| Samsung WB1000 | samsung_wb1000 | samsung_slb_11a | promoted_verified | verified_medium source satisfies promotion policy. |
| Samsung TL320 | samsung_wb1000 | samsung_slb_11a | promoted_verified | verified_medium source satisfies promotion policy. |
| Sony DSC-RX10 | sony_cyber_shot_dsc_rx10 | sony_np_fw50 | promoted_verified | verified_high source satisfies promotion policy. |
| Sony DSC-HX30V | sony_cyber_shot_dsc_hx30v | sony_np_bg1 | promoted_verified | verified_high source satisfies promotion policy. |
| Sony DSC-W530 | sony_cyber_shot_dsc_w530 | sony_np_bn1 | promoted_verified | verified_high source satisfies promotion policy. |
| Fujifilm FinePix F31fd | fujifilm_finepix_f31fd | fujifilm_np_95 | already_verified | Verified mapping already existed before this research batch. |
| Panasonic TZ70 / ZS50 | panasonic_lumix_dmc_zs50 | panasonic_dmw_bcm13pp | promoted_verified | verified_high source satisfies promotion policy. |
| Nikon Coolpix S9500 | nikon_coolpix_s9500 | nikon_en_el12 | already_verified | Verified mapping already existed before this research batch. |
| Casio Exilim EX-ZR1000 | casio_exilim_ex_zr1000 | casio_np_130 | already_verified | Verified mapping already existed before this research batch. |
| Kodak EasyShare C613 | kodak_easyshare_c613 | generic_aa | promoted_verified | verified_medium source satisfies promotion policy. |

## Alias Corrections

- Removed conflicting ZS50 alias from panasonic_lumix_dmc_tz50; Panasonic manual associates ZS50 with TZ70.

## Selected Tasks Still Awaiting Evidence

| Camera | Brand | Search queries prepared | Reason |
| --- | --- | ---: | --- |
| Sony Cyber-shot DSC-HX1 | Sony | 15 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Nikon COOLPIX P1 | Nikon | 14 | Research task generated; no reviewed battery evidence recorded in this batch. |
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
| Sony Cyber-shot DSC-HX100V | Sony | 15 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Nikon COOLPIX P100 | Nikon | 14 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Fujifilm FinePix F401 | Fujifilm | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Panasonic Lumix DC-LX100 II | Panasonic | 12 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Olympus Stylus 500 | Olympus | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Samsung ST30 | Samsung | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Casio Exilim EX-ZR100 | Casio | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Kodak EasyShare C122 | Kodak | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Pentax Optio 30 | Pentax | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Ricoh CX1 | Ricoh | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| HP PhotoSmart 210 | HP | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| MINOLTA DiMAGE G500 | Minolta | 12 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Konica Minolta DiMAGE A200 | Konica Minolta | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Leica C-Lux 1 | Leica | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Sigma DP1 | Sigma | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Sony Cyber-shot DSC-HX5V | Sony | 15 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Nikon COOLPIX P2 | Nikon | 14 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Fujifilm FinePix F470 | Fujifilm | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Panasonic Lumix DC-ZS80 | Panasonic | 12 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Olympus μ 5000 | Olympus | 10 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Samsung ST500 | Samsung | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |
| Casio Exilim EX-ZR15 | Casio | 11 | Research task generated; no reviewed battery evidence recorded in this batch. |

## Twenty Popular Models Still Unresolved

| Camera | Brand | Current reason |
| --- | --- | --- |
| Sony Cyber-shot DSC-HX1 | Sony | Camera existence confirmed, battery not yet source-verified |
| Sony Cyber-shot DSC-HX100V | Sony | Battery source check failed: TimeoutError: The read operation timed out |
| Sony Cyber-shot DSC-HX5V | Sony | Camera existence confirmed, battery not yet source-verified |
| Sony Cyber-shot DSC-HX7V | Sony | Camera existence confirmed, battery not yet source-verified |
| Sony Cyber-shot DSC-HX9V | Sony | Camera existence confirmed, battery not yet source-verified |
| Sony Cyber-shot DSC-RX10 II | Sony | Checked source but no explicit battery/power mapping was extracted. |
| Sony Cyber-shot DSC-T11 | Sony | Camera existence confirmed, battery not yet source-verified |
| Sony Cyber-shot DSC-T110 | Sony | Battery source check failed: TimeoutError: The read operation timed out |
| Sony Cyber-shot DSC-T2 | Sony | Camera existence confirmed, battery not yet source-verified |
| Sony Cyber-shot DSC-T20 | Sony | Camera existence confirmed, battery not yet source-verified |
| Sony Cyber-shot DSC-T25 | Sony | Camera existence confirmed, battery not yet source-verified |
| Sony Cyber-shot DSC-T30 | Sony | Camera existence confirmed, battery not yet source-verified |
| Sony Cyber-shot DSC-T5 | Sony | Camera existence confirmed, battery not yet source-verified |
| Sony Cyber-shot DSC-T66 | Sony | Camera existence confirmed, battery not yet source-verified |
| Sony Cyber-shot DSC-T75 | Sony | Camera existence confirmed, battery not yet source-verified |
| Sony Cyber-shot DSC-T99 | Sony | Camera existence confirmed, battery not yet source-verified |
| Sony Cyber-shot DSC-TX1 | Sony | Camera existence confirmed, battery not yet source-verified |
| Sony Cyber-shot DSC-TX10 | Sony | Camera existence confirmed, battery not yet source-verified |
| Sony Cyber-shot DSC-TX100V | Sony | Checked source but no explicit battery/power mapping was extracted. |
| Sony Cyber-shot DSC-TX300V | Sony | Battery source check failed: TimeoutError: The read operation timed out |
