# Stramin SwiftUI Prototype

This directory contains a lightweight reference UI for Stramin's normalized
`daily_state.json` contract.

It is intentionally standalone:

- no Xcode project files
- no dependency on the Python runtime
- no effect on automation, Telegram delivery, GarminDB sync, or tests

## Usage

1. Create a new SwiftUI app in Xcode.
2. Replace the generated `ContentView.swift` with this directory's
   `ContentView.swift`.
3. Run the app preview or simulator.

The view currently uses embedded mock JSON based on a verified Stramin
`daily_state.json` example. Future app work can replace the mock JSON with a
file load, API response, or local app-group state reader.

## Mock State

The sample renders:

- recovery date: `2026-05-10`
- validation status: `ready`
- sleep: `7.43`
- HRV: `34 ms`
- stress: `34`
- resting HR: `59`
- recommendation: `train / normal / weight_training`
