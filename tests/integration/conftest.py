"""Fixtures for wallet integration tests.

- ``running_wallet``: a Client bound to the developer's already-open wallet.
  Skips when no control socket is present.
- ``ephemeral_wallet``: a throwaway isolated wallet instance (session-scoped,
  so it's launched once and reused for speed). Skips when the app is absent.
- ``fresh_wallet``: a brand-new ephemeral instance per test, for assertions
  that require a pristine wallet.

There is no per-test vault cleanup: tests share the session ``ephemeral_wallet``
and use unique vault names rather than deleting vaults (an open vault holds LMDB
locks, so deleting its files mid-run is fragile). Tests that genuinely need a
guaranteed-empty wallet use ``fresh_wallet`` instead.
"""
import os

import pytest

from driver.client import Client, default_socket_path
from driver.instance import EphemeralWallet, LOCKSMITH_BINARY


@pytest.fixture
def running_wallet():
    path = default_socket_path()
    if not os.path.exists(path):
        pytest.skip("no running wallet control socket; launch Locksmith first")
    return Client(socket_path=path)


@pytest.fixture(scope="session")
def ephemeral_wallet():
    if not os.path.exists(LOCKSMITH_BINARY):
        pytest.skip(f"Locksmith app not installed at {LOCKSMITH_BINARY}")
    with EphemeralWallet() as wallet:
        yield wallet


@pytest.fixture
def fresh_wallet():
    """A brand-new ephemeral wallet per test, for assertions that require a
    pristine instance (the session-scoped ``ephemeral_wallet`` accumulates
    state — vaults created by earlier tests — across the run)."""
    if not os.path.exists(LOCKSMITH_BINARY):
        pytest.skip(f"Locksmith app not installed at {LOCKSMITH_BINARY}")
    with EphemeralWallet() as wallet:
        yield wallet
