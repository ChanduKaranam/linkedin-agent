# frontend/lib/

## Purpose
Shared utility code for the frontend. Currently contains only the typed API client used by components to communicate with the Next.js API proxy routes.

## Files
| File | Purpose |
|---|---|
| `api.ts` | Typed fetch helpers. Exports functions like `fetchTrendDates()`, `fetchTrendsByDate(date)`, `fetchTrendDetail(date, slug)`, `triggerSearch(topic)`, `fetchSearchHistory()`, `postChatMessage(base, history, message)`. Centralises error handling and base URL config. |

## Last Session Changes
_No changes recorded yet. Run `/end` at session close to record changes._

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| — | — | Initial documentation created |
