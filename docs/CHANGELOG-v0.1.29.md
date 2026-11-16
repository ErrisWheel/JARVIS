# J.A.R.V.I.S. v0.1.29

## Conversation restore orientation fix

- Normalize nullable and invalid persisted orientation values before either branch of conversation restoration.
- Normalize again when converting restored message records into `ChatLine` state.
- Type the final restored collection as `ChatLine[]` so strict TypeScript checks guard this boundary.
- Add regression coverage for portrait, landscape, null, missing, and invalid orientation values.
- No model, dependency, database, or image-generation runtime changes.
