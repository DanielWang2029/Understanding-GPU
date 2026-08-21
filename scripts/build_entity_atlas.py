#!/usr/bin/env python3
"""Superseded entry point, kept because it is the command the docs quote.

The atlas is now one stage of the standardised pipeline in `pipeline/atlas`,
which emits the source, record and entity registries alongside the UI bundles.
See docs/DATA-PIPELINE.md.

    python3 -m pipeline.atlas.build
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pipeline.atlas.build import main  # noqa: E402

if __name__ == "__main__":
    print("note: build_entity_atlas.py now delegates to pipeline.atlas.build\n")
    sys.exit(main())
