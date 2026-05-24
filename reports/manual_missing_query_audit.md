# Manual Missing Query Audit

Generated: 2026-05-25

## Summary

- total manual query notes: 4
- search_alias_fixed: 2
- unresolved_battery: 2

## Rows

| Query | Status | Expected brand | Expected model | Catalog state | Matched camera_id | Recommended action | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| canon ixy500 | search_alias_fixed | Canon | IXY DIGITAL 500 | verified_camera | canon_powershot_s500_digital_elph | No data action; keep search regression test. | Data existed as Canon PowerShot S500 DIGITAL ELPH / DIGITAL IXUS 500 / IXY DIGITAL 500. |
| sony t700 | search_alias_fixed | Sony | DSC-T700 | verified_camera | sony_cyber_shot_dsc_t700 | No data action; keep search regression test. | Data existed as Sony Cyber-shot DSC-T700. |
| fuji f30 | unresolved_battery | Fujifilm | FinePix F30 | unresolved_candidate | fujifilm_finepix_f30 | Find explicit battery source before promoting. | Candidate exists in camera_candidates.json, but no explicit source-backed battery mapping is stored yet. |
| panasonic tz90 | unresolved_battery | Panasonic | Lumix DC-ZS70 / TZ90 | unresolved_candidate | panasonic_lumix_dc_zs70 | Find explicit battery source before promoting. | Candidate exists in camera_candidates.json, but no explicit source-backed battery mapping is stored yet. |
