# Database Schema and Migrations

Place your SQL migration scripts and database schema definitions here. Tools like [dbmate](https://github.com/dbmate/dbmate) or [Flyway](https://flywaydb.org/) can be used to manage migrations.

Recommended tables:

- `generic_events` – stores all raw on‑chain events indexed per contract address, topic and data.
- `erc20_transfers` – parsed ERC‑20 `Transfer` events.
- `erc721_transfers` – parsed ERC‑721 `Transfer` events.
- `alerts` – stores generated alert records.
