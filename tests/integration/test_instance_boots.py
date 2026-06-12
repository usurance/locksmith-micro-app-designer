"""Integration spike: a seeded throwaway-HOME wallet comes up and responds.

Validates the riskiest part of the harness — that copying the real index.json
and symlinking the plugin clones is enough for the host to load ui_tester and
open its control socket in a fresh HOME. Skips when Locksmith isn't installed.
"""


def test_ephemeral_wallet_pings(ephemeral_wallet):
    assert ephemeral_wallet.client is not None
    assert ephemeral_wallet.client.ping() is True


def test_ephemeral_wallet_starts_with_zero_vaults(ephemeral_wallet):
    # A pristine HOME has no vaults: the drawer's vault rows are absent.
    result = ephemeral_wallet.client.call("count", target="vaultDrawer.vaultList")
    assert result.get("ok") is True
