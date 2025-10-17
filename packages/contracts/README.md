# Contract ABIs and Event Schemas

This directory should contain ABI definitions (JSON) for supported smart contracts as well as typed event schema definitions used by the indexer. Example:

- `ERC20.json` – ABI for ERC‑20 contracts
- `ERC721.json` – ABI for ERC‑721 contracts

Typed event schemas help the indexer decode raw `GenericEvent` rows into meaningful tables.
