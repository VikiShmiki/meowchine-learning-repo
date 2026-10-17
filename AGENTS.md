# Smart Recycling Access

Mobile-first guidance for correct disposal, plus city tools for finding and closing
recycling-access gaps. The canonical product brief is [PROJECT_BRIEF.md](PROJECT_BRIEF.md).

## Start here

1. Read [STATUS.md](STATUS.md) for current work and blockers.
   Follow its active task when one is listed; otherwise use the current state and
   the user's request. Do not start pending implementation tasks.
   Apply [docs/ENGINEERING.md](docs/ENGINEERING.md) to every change and consult
   [docs/DELIVERY_PLAN.md](docs/DELIVERY_PLAN.md) for scope and acceptance criteria.
2. Open only the document relevant to the task:
   - Product scope: [docs/PRODUCT.md](docs/PRODUCT.md)
   - System boundaries: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
   - Data contracts: [docs/DATA.md](docs/DATA.md)
   - Model and evaluation: [docs/ML.md](docs/ML.md)
   - HTTP contract: [docs/API.md](docs/API.md)
   - Tests and delivery: [docs/QUALITY.md](docs/QUALITY.md)
   - Lasting choices: [docs/DECISIONS.md](docs/DECISIONS.md)
   - Bilingual behavior: [docs/LANGUAGES.md](docs/LANGUAGES.md)
   - Citizen destinations and trips: [docs/ROUTING.md](docs/ROUTING.md) and
     [docs/MAP.md](docs/MAP.md)
   - City coverage and upgrades: [docs/CITY_MODE.md](docs/CITY_MODE.md)
   - Reports and accounts: [docs/COMMUNITY.md](docs/COMMUNITY.md) and
     [docs/ACCOUNTS.md](docs/ACCOUNTS.md)
   - Hosted CI exception: [docs/CI_STATUS.md](docs/CI_STATUS.md)

## Working rules

- Keep one deployable service until scale proves otherwise.
- Prefer a tested baseline over an unmeasured complex model.
- Use canonical labels: `glass`, `plastic_metal`, `paper_tetrapak`, `general`,
  `special_unsupported`. Abstention is not a class.
- Make experiments repeatable (`seed=42`) and record data/model versions.
- Never commit secrets, personal location history, or unlicensed raw data.
- Add or update tests with behavior; run `make check` before handoff.
- Keep docs concise; update `STATUS.md` when priorities or capabilities change.
- Match the existing commit style: `docs:`, `feat:`, `fix:`, `test:`, `build:`,
  `ci:`, or `refactor:` followed by a concise, specific description. Use the same
  format for PR titles and squash commits; keep unrelated changes separate.
