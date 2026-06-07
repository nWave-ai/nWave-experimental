"""Outcomes registry — production module (replaces nwave_ai.outcomes.spike).

Hexagonal layout:
    domain/       — Outcome value object, ShapeNormalizer
    application/  — RegistryService, CollisionDetector
    ports/        — RegistryReader/Writer Protocols
    adapters/     — YamlRegistryAdapter (real filesystem I/O)
    cli.py        — argparse register/check subcommands
"""
