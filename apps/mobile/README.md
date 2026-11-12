# Recruiting Platform Mobile (`apps/mobile`)

Cross-platform mobile application built with **Expo SDK 51**, **React Native 0.74**, and **`expo-router` v3**.

---

## Features

- **Persona-Tailored Chat Interface**: Dynamically adjusts greeting prompts, placeholders, and action buttons for Students, Placement Officers, Companies, and Recruiters.
- **Voice Mic Integration**: Built-in audio recording via `expo-av`, streaming voice messages directly to the FastAPI Whisper transcription endpoint.
- **Resume Upload & Consent Flow**: Ingestion of PDF/DOCX resumes for Students with pre-upload consent confirmation modals.
- **Offline & Emulator Networking**: Automated localhost to `10.0.2.2` mapping for seamless Android Emulator development.
- **Expo Application Services (EAS)**: Configured build profiles for preview APK generation.

---

## Quickstart

### 1. Prerequisites

- Node.js ≥ 20
- pnpm ≥ 9
- Android Studio (for Android Emulator) or Xcode (for iOS Simulator)
- EAS CLI: `npm install -g eas-cli`

### 2. Environment Variables

Create `.env` in `apps/mobile`:

```ini
EXPO_PUBLIC_SUPABASE_URL=https://bsegerbrkbxnosyojmwf.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOi...
EXPO_PUBLIC_API_BASE_URL=http://10.0.2.2:8000
ENVIRONMENT=development
```

> **Note for Android Emulator**: Use `http://10.0.2.2:8000` to communicate with the FastAPI backend running on your host machine.

### 3. Run Locally

```bash
# Start Expo development server
pnpm start

# Press 'a' in the terminal to launch on Android Emulator
# Press 'i' to launch on iOS Simulator
```

---

## EAS Cloud Builds

The project uses EAS Build with `apps/mobile/eas.json`:

```bash
# Build standalone Android APK under preview profile
eas build --platform android --profile preview
```
