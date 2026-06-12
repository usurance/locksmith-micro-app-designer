"""Fixtures for wallet integration tests.

- ``running_wallet``: a Client bound to the developer's already-open wallet.
  Skips when no control socket is present.
- ``ephemeral_wallet``: a throwaway isolated wallet instance (session-scoped).
  Skips when the Locksmith app is not installed.
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
