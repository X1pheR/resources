# Hypershell SDLC checker (public distribution)

This is a checked, derived copy of the one canonical checker maintained in the private `X1pheR/hypershell-infrastructure` repository, not a second checker implementation.

- Canonical source: `0c26d43d47c14d0a1d0da1be4b61d43f9ff71707`
- Private merge: `6f5a51eafdcc9df4039a79f3c2920845661f7cd8`
- License: MIT, included in the script
- Runtime: Python 3.12+ and Git, no pip dependencies for the public mode

Verify `sha256sum -c SHA256SUMS`, then run `python3 sdlc-conformance.py --public-repo /path/to/checkout --json`.

Exit 0: static public patch register passes; exit 1: fail-closed finding; exit 2: invalid invocation. The source-owned `pr_state` field is not live GitHub evidence. This checker does not verify release inclusion, private ADRs, source/runtime parity or production. Private exception metadata is never distributed. Pin an immutable `resources` commit plus this artifact SHA-256 before use; subsequent artifacts must be produced from the canonical infrastructure owner.
