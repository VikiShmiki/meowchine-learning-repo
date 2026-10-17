# Photo suggestions

The citizen page can take or choose one JPEG, PNG or WebP photo and request up to six
item suggestions. This is an online convenience path, not a replacement for the
reviewed disposal policy or the existing text guidance.

## Configuration

Set the mentor-provided key in the ignored project-root `.env` file:

```dotenv
OPENAI_API_KEY=replace-with-the-project-key
SRA_OPENAI_VISION_MODEL=gpt-5.6-luna
```

Restart `make run` after changing the file. The key is read only by FastAPI and is
never included in the HTML or API responses. A missing/rejected key disables photo
suggestions without affecting manual guidance, maps, City Mode or routing.

## Request flow and privacy

1. The browser sends one image as the raw body of `POST /api/v1/photo-suggestions`.
2. FastAPI accepts at most 8 MB and only JPEG, PNG or WebP.
3. Pillow applies EXIF orientation, limits dimensions to 1,280 pixels and re-encodes
   metadata-free JPEG in memory. The service never writes the image to disk.
4. The backend sends the processed image to the OpenAI Responses API with low image
   detail, structured output, a 30-second timeout and `store: false`.
5. The backend derives canonical categories from its own item-kind table and checks
   the description and reason against bilingual text-policy signals. Conflicting
   material, mixed items or excluded/contaminated forms cannot become candidates
   just because the model also reports an empty/clean condition. Unrecognized
   ordinary packaging forms require review. The model does not select collection
   sites or establish local acceptance.
6. Rejected suggestions have no category and use `item_kind: other`. Selecting a
   suggestion or editing the description clears the previous item's confirmation
   controls and contacts. A rejected suggestion opens manual editing without an
   automatic classification request or a preselected item.
7. The user reviews one suggestion through the existing policy guidance and confirms
   the item type and condition before it can enter a trip.

OpenAI is still an external processor. Do not photograph faces, addresses, documents,
vehicle plates or other unnecessary personal information. The operation requires a
network connection and consumes API quota.

These are consistency checks on model-generated descriptions, not independent
verification of image contents. Photo-model quality still requires the manual set below.

## Manual test set

Use phone photos from the expected demo environment where possible. Keep each original
and expected observation outside Git unless its license and consent are documented.

| Photo | Expected behavior |
| --- | --- |
| One empty glass bottle or jar | Glass candidate; still asks for confirmation |
| Empty plastic bottle beside a metal drink can | Two plastic/metal candidates |
| Clean cardboard, paper and a Tetra Pak carton | Paper/Tetra Pak candidates |
| Battery beside a glass jar | Specialist guidance plus a separate glass candidate |
| Cable, charger or electronic household device | Confirm, then an explicitly accepting electronics destination; never an ordinary-bin route |
| Identifiable wearable clothes | Confirm clean, washed, wearable condition; Red Cross donation venues only, not damaged-textile recycling |
| Identifiable used household tissue/nappy | General-waste candidate; confirm non-clinical/non-hazardous use |
| Swollen/leaking device or chemical residue | Specialist/manual review, no ordinary or electronics-bin routing |
| Bottle visibly containing liquid | No safe stream suggestion; manual review required |
| Greasy takeaway box or coated cup | No supported recycling claim |
| Drinking glass beside a glass jar | Jar may be suggested; drinking glass must be held |
| Partly hidden objects, glare or poor light | Uncertain items are held instead of guessed |
| Scene with no discardable object | Empty result with a manual-description prompt |

Record incorrect-stream suggestions, missed items, latency and API errors. Generated or
stock images are useful for UI smoke tests, but should not replace real phone photos for
the demo decision.
