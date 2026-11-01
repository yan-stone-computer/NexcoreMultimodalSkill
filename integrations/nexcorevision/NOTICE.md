# NexcoreVision integration

The TypeScript visual-evidence pipeline in this directory is vendored from
[`yan-stone-computer/NexcoreVision`](https://github.com/yan-stone-computer/NexcoreVision)
at commit `b8fa979` (2026-10-30).

It is distributed under the MIT License in `LICENSE`. The wrapper in
`scripts/nexcore_vision.py` treats this pipeline as the primary visual-evidence
architecture and keeps the legacy Python multi-engine route available as a
document parser and fallback.
