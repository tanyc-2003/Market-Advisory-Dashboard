# Vendored: Kronos

Source: https://github.com/shiyu-coder/Kronos (branch master), files `model/`.
License: Apache-2.0 (see LICENSE). Model weights: NeoQuasar/Kronos-* on Hugging Face.

Local modifications: the intra-package import in `kronos.py`
(`from model.module import *`) was changed to the relative `from .module import *`
so the code works when vendored under `src/advisory/layer_kronos/kronos_vendor/`.
No model logic was changed.
