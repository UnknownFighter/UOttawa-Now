"""Source adapters. Each file in this folder exposes  fetch(account, limit) -> (info, [Post, ...]).
To add a new source later (a website, an email inbox...), add a file here with the same function."""
import importlib


def get_source(name):
    return importlib.import_module(f"pipeline.sources.{name}")
