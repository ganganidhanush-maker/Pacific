# 3D Digital Human (VRM) Asset Pipeline for Octopus AI

## Overview
Octopus AI supports **persistent 3D digital human avatars** using the **VRM** open humanoid specification. The 3D avatar is rendered in real time in WebGL using **Three.js** and **`@pixiv/three-vrm`**, driven directly by:
1. **Chatterbox Cloned Neural Voice**: Real-time spectral audio viseme lip-sync (`aa`, `ih`, `ou`, `ee`, `oh`).
2. **Procedural Motion Engine**: Continuous natural breathing, Poisson-distributed autonomous blinking, eye gaze tracking, and state-reactive head nods and tilts.
3. **Canonical Motion Profile**: Calibrated against Dhanush's studio video takes via `dhanush_motion_profile.json`.

---

## Canonical Model Placement
To set your canonical digital human model:
1. Name your exported VRM file: `dhanush.vrm`
2. Place it in this folder: `octopus_ai/assets/avatars/dhanush.vrm`
3. Octopus AI will automatically load `dhanush.vrm` on startup!

---

## How to Create & Export Dhanush.vrm

### Option 1: Free VRoid Studio (Recommended for Fast High-Fidelity Customization)
1. Download **VRoid Studio** (free for Windows/Mac): [https://vroid.com/en/studio](https://vroid.com/en/studio).
2. Customize facial features, hair, eye shape, and clothing (e.g. polo shirt / collared shirt) to match Dhanush's studio look.
3. Click **Export as VRM** (`.vrm`).
4. Select standard humanoid blendshapes (`aa`, `ih`, `ou`, `ee`, `oh`, `blink`, `happy`, `relaxed`).
5. Save the file as `dhanush.vrm` in this folder.

### Option 2: ReadyPlayerMe (Photo-to-3D Generator)
1. Visit [https://readyplayer.me/avatar](https://readyplayer.me/avatar).
2. Take a photo or upload Dhanush's front-facing face photo.
3. Customize hair and outfit.
4. Export as `.vrm` (or `.glb` converted to `.vrm` in Blender using the VRM addon).
5. Save as `dhanush.vrm` in this folder.

### Option 3: Blender / Parametric Mesh (FLAME / SMPL-X)
1. Use the open-source **Blender VRM Addon** ([https://github.com/saturday06/VRM_Addon_for_Blender](https://github.com/saturday06/VRM_Addon_for_Blender)).
2. Ensure standard VRM 0.0 or VRM 1.0 humanoid bone rig:
   - `Hips`, `Spine`, `Chest`, `Neck`, `Head`
   - `LeftEye`, `RightEye`
3. Blendshapes required for full Octopus AI lip-sync and emotion support:
   - Visemes: `aa`, `ih`, `ou`, `ee`, `oh`
   - Eyes: `blink`, `blinkLeft`, `blinkRight`
   - Emotions: `neutral`, `happy`, `relaxed`, `surprised`

---

## Motion & Audio Configuration
The file `dhanush_motion_profile.json` in this directory contains the mathematical parameters extracted from Dhanush's studio video takes:
- **Breathing**: 0.31 Hz sine oscillation on chest and spine.
- **Blinking**: Average interval of 3.8s with natural close/hold/open velocity.
- **Lip-Sync FFT**: Vowel formant frequency bands (F1 & F2) mapped directly from audio soundwaves to mouth blendshapes.
