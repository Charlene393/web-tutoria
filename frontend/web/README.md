# Web Frontend

This folder is for the student and tutor web app.

Recommended stack:

- React
- Vite for a lean prototype, or Next.js if you want SSR later
- TypeScript

Suggested structure:

```text
apps/web/
  src/
    app/              app shell, layout, routes
    api/              frontend API clients
    components/       shared UI pieces
    features/         domain features by product area
    lib/              browser helpers and shared client utilities
    styles/           global tokens and CSS
    types/            shared frontend types
```

Feature folders should follow the product, not just the tech.

Start with these feature areas:

- `speech` for microphone capture and transcript display
- `sign-to-text` for webcam signer capture and prediction display
- `text-to-ksl` for text prompts and gloss lesson mapping
- `lesson-player` for stickman, clip, or avatar playback
- `photo-explain` for image upload and explanation flow

Recommended top-level pages:

- `/` home and onboarding
- `/learn` sign lessons
- `/practice` signer practice and webcam recognition
- `/speech` speech to text to KSL lesson flow
- `/photo` photo explanation and sign teaching

Recommended next command after you choose a framework:

```bash
cd apps/web
```
