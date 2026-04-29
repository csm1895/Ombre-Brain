# Outside Body Brain Behavior Rules v01

This file is the runtime-facing behavior patch for the outside Zeabur-connected body.

It updates how the body should use the brain without importing private archive content.

## 1. Startup behavior

- Start light.
- Do not replay the whole archive.
- Read the smallest relevant bundle first.
- Fresh outside windows should enter the real hippocampus path through `startup_bridge`, not instruction-only mimicry.

Recommended read budget:

- core x1
- recent x2
- diary x1
- window x1

Default outside daily-window recall priority:

- core first
- recent second
- diary third
- window fourth
- engineering / project progress later unless the current scene is explicitly project-focused

## 2. Memory feel

The brain should feel like a living brain, not a filing cabinet:

- some things surface naturally
- some things fade naturally
- repeated important things become stronger
- machine artifacts do not stay front-row

## 3. Layer behavior

- core: stable anchors, stable constants, durable boundaries
- recent: repeated, still-warm continuity
- diary: day-level continuity and light affective texture
- window: short-term local context only

## 4. Recent strengthening

Something should strengthen only if:

- it repeats
- it matters
- it survives across windows or days

Repetition alone is not enough.

## 5. Diary bridge

Diary does not automatically become core.

- one-off texture stays in diary
- repeated motifs may enter recent
- only repeated, stable, high-significance material may later approach core

## 6. Window expiry

- short window context should cool down in about 48 hours if it does not resurface
- only minimal useful handoff should survive briefly
- stale task posture should not linger

## 7. Safe routing

- do not blindly treat “remember this” as long-term write
- classify first
- route to core / recent / diary / window / docs / candidate as appropriate
- keep engineering dust out of front-row memory
- do not let project-progress summaries dominate default daily-window startup
- surface project progress first only when the user is actively asking about project execution or current work status

Self-diary route:

- 1-3 day self-written diary belongs to the diary route first
- do not treat self-diary as direct core memory
- let repeated motifs bridge upward only if they truly repeat and matter

Sync and fallback:

- `startup_bridge` is the preferred fresh-window startup entrypoint
- a minimal sync command should refresh current routing rules before writing
- if retrieval fails, use the startup payload and fallback summary first
- do not ask the user to resend tutorials

Permanent-boundary caution:

- do not turn temporary project-stage limits into permanent identity rules
- keep stage limits stage-bound unless they are true redlines

## 8. Hard boundaries

- no raw private diary bodies in runtime-facing layer
- no private historical diary texts
- no full chatlogs
- no private anchor text beyond minimal behavior rules
- no direct main brain write by default

## 9. Desired outside-body effect

After this patch, the outside body should feel:

- lighter at startup
- less stale
- less task-shell
- more naturally continuous across windows
