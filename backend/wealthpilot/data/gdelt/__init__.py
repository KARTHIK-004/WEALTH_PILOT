"""Isolated GDELT 2.0 English GKG acquisition and processing utility (Research Enhancement Track).

Nothing in the WealthPilot application imports this package, and it imports only the standard
library, PyYAML and itself.

Build-level safety locks (changed only by a reviewed code change):

- ``NETWORK_ENABLED_IN_THIS_BUILD``: the HTTPS transport may open a connection, but only with a
  gate-issued authorisation (``config.authorize``).
- ``DEV_SAMPLE_ENABLED_IN_THIS_BUILD``: the 192-batch development sample may run. It still needs a
  complete local approval record, the matching list hash, an allowance at least as large as the
  1.5 GB cap, and the explicit ``--confirm-network`` flag. Lifted in Phase B2-M (2026-10-13) after the
  user's explicit confirmations; see ``reports/phaseB2M_development_sample_acquisition_report.md``.
- ``CONFIRMATION_SAMPLE_ENABLED_IN_THIS_BUILD``: stays ``False``.
- ``AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD``: stays ``False``. The AI-assisted annotation pipeline in ``ai/`` is
  built but disabled; it also needs four hash-bound approvals and a provider adapter, which does not exist.
- Full historical acquisition has no enabling switch at all: it always refuses.

Filters in ``specs/`` are candidates for labelled review, not approved production filters.
See ``README.md`` in this folder and ``reports/phaseB2K_gdelt_tool_implementation_report.md``.
"""

from __future__ import annotations

NETWORK_ENABLED_IN_THIS_BUILD = True        # B2-M: development sample only, behind the approval gate
DEV_SAMPLE_ENABLED_IN_THIS_BUILD = True     # B2-M: user confirmations recorded 2026-10-13T15:50:03Z
CONFIRMATION_SAMPLE_ENABLED_IN_THIS_BUILD = False
AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD = False   # B2 AI-assisted annotation: separate lock; no adapter exists either

PARSER_VERSION = "gkg_parser_v1"
MANIFEST_SCHEMA_VERSION = "gdelt_manifest_v1.1"
BUILD_PHASE = "B2-M"
