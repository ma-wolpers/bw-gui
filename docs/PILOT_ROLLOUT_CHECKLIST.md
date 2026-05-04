# Pilot Rollout Checklist

## Blattwerk

- Replace direct imports of local ui_contract modules.
- Wire themed menu strip to shared `CustomMenuBar` where applicable.
- Keep app-specific menu actions local.
- Validate shortcuts, popup handling, and preview/editor modes.

## Kursplaner

- Replace direct imports of local ui_contract modules.
- Adopt shared theming calls from `bw_gui.theming`.
- Keep domain-specific toolbar logic, but switch to shared tooltip and label helpers.
- Validate grid actions, shortcut overlays, and hover help text.

## Cross-pilot acceptance

- No native menubar in migrated windows.
- Buttons remain icon-first where expected.
- Hover explanations include shortcut hints.
- All tests and guardrails pass in each pilot repo.
