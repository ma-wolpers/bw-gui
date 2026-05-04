# Submodule Consumer Setup

This project is consumed via git submodule.

## 1) Add submodule in a consumer repo

From the consumer repo root, run:

- `git submodule add ../bw-gui bw-gui`
- `git submodule update --init --recursive`

Expected layout example:

- consumer-repo/
- consumer-repo/bw-gui/
- consumer-repo/bw-gui/src/bw_gui/

## 2) Ensure import path

Option A (recommended): install editable package in consumer venv.

- `a:/Code/<consumer>/.venv/Scripts/python.exe -m pip install -e ./bw-gui`

Option B: add `bw-gui/src` to runtime path in consumer bootstrap.

## 3) Replace local duplicate modules

Map local modules to shared imports:

- local ui_contract/keybinding -> `bw_gui.contracts.keybinding`
- local ui_contract/popup -> `bw_gui.contracts.popup`
- local ui_contract/hsm -> `bw_gui.contracts.hsm`

## 4) Pilot rollout order

1. blattwerk
2. kursplaner
3. namenfit
4. korrektor
5. kartograph

## 5) CI updates

- Add submodule checkout in CI clone phase.
- Install shared package before running tests.
