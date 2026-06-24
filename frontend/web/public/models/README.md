# Avatar Models

Place a VRM avatar at:

```text
frontend/web/public/models/avatar.vrm
```

The lesson player will automatically use that model when the file exists. Until then,
it falls back to the procedural Three.js humanoid so landmark playback can be tested
without blocking on asset selection.
