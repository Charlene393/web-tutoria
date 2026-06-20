# Pipelines

Use this folder when one user action requires several coordinated steps.

Examples:

- speech input -> transcript -> KSL gloss mapping -> lesson lookup
- signer input -> landmark cleanup -> model inference -> text output
- photo upload -> object detection -> explanation -> lesson lookup

If a service becomes too large, move the multi-step orchestration here.
