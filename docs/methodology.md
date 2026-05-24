# Collection Methodology

## Source Priority

1. Official manufacturer manuals or specification pages.
2. Official manufacturer accessory compatibility pages.
3. Trusted camera databases or manual mirrors, preferably corroborated.
4. Retailers or third-party battery charts.
5. If no source confirms a mapping, record `unknown`; do not guess.

## Confidence Rules

- `high`: official manufacturer manual/specification/accessory page confirms the
  battery or battery system.
- `medium`: trusted database, official manual mirrored by a third party, or more
  than one non-official source agrees.
- `low`: retailer, third-party chart, single non-official source, or source only
  partially identifies the system.

## Naming Rules

- `display_name` is the canonical display name used in this database.
- `aliases` contains spelling variants and kit/body variants.
- `regional_names` captures market names, for example Canon PowerShot / Digital
  IXUS / IXY Digital, or Panasonic ZS / TZ variants.

## Battery System Rules

- `proprietary_li_ion`: removable named rechargeable pack such as Canon NB-13L.
- `aa`: camera uses AA cells; record quantity in compatibility.
- `aaa`: camera uses AAA cells; record quantity in compatibility.
- `built_in`: rechargeable cell is built into the camera and not user removable.
- `special`: removable non-AA/AAA battery format that is not a named
  rechargeable camera pack, for example 2CR5 lithium.
- `unknown`: no source-backed battery system has been confirmed yet.

Special or mixed-power cases are represented with multiple compatibility rows or
with a precise `note`. For example, a camera that supports CR-V3 or two AA cells
gets one row for CR-V3 and one row for AA.

If the source confirms AA/AAA use but does not state the cell count, keep
`quantity_required` as `null` and explain the source wording in `note`; do not
fill a guessed quantity.

## No-Inference Rule

Never map a camera to a battery solely because another camera in the same family
uses that battery. Add the mapping only when the exact camera model is listed by
the source.
