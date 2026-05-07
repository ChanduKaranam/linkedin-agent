# frontend/src/components/layout/

## Purpose
This folder contains shared layout shell components used across page routes in the frontend app. It centralizes top-level navigation, workspace switching, and page transition behavior so route pages can focus on feature content. Keeping layout concerns isolated here ensures consistent app framing and global header interactions.

## Files
| File | Purpose |
|---|---|
| `AppLayout.tsx` | Global page wrapper that renders `Navbar` and animates route content transitions with `AnimatePresence`/`motion` |
| `Navbar.tsx` | Main header/navigation bar with workspace toggle, LinkedIn connection state/action, schedule editor access, and route nav links |

## Last Session Changes
**Session date:** 2026-05-06

**Changes made:**
- FOLDER.md created by `/create` — initial documentation pass.

**Reason:** Bootstrapping project documentation so that `/start` and `/end` can be used going forward.

**Outcome:** Complete — all files documented as of this date.

**Watch out for:** This documentation was generated from a static read of the code. If any files have changed since this was written, run `/end` after your next session to keep it current.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-06 | Initial creation | FOLDER.md bootstrapped by `/create` |
