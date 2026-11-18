---
name: TIG Recruitment Workspace
colors:
  primary: "#c2410c"
  neutral: "#ffffff"
  ink: "#0f172a"
typography:
  h1:
    fontFamily: system-ui
    letterSpacing: "-0.025em"
---

## Overview

Preserve the existing Operate workspace and orange accent. Creation is a Configure surface: metadata followed immediately by the existing requirements editor, one form and one explicit save. No redesign or new scoring concepts.

## Layout

Lowongan displays metadata and discoverable requirements; Lamaran displays the selected vacancy's application queue and evidence. Hash navigation supports browser back/refresh without losing the current selection during view changes. Keep controls responsive and keyboard accessible.

## Components

Reuse current inputs, panels, buttons and typography. Show active navigation via aria-current. Creation failures retain inputs; a successful metadata POST is retained for config-only retries. Publication is submitted only with the complete config, never during metadata creation.
