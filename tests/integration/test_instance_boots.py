"""Integration spike: a seeded throwaway-HOME wallet comes up and responds.

Validates the riskiest part of the harness — that copying the real index.json
and symlinking the plugin clones is enough for the host to load ui_tester and
open its control socket in a fresh HOME. Skips when Locksmith isn't installed.
"""


def test_ephemeral_wallet_pings(ephemeral_wallet):
    assert ephemeral_wallet.client is not None
    assert ephemeral_wallet.client.ping() is True


def test_fresh_wallet_has_zero_vaults(fresh_wallet):
    # A pristine HOME has no vaults: the drawer's vault list has no entries.
    # Uses fresh_wallet (its own instance) — the shared session wallet
    # accumulates vaults from other tests. (count on vaultDrawer.vaultList would
    # return 1 — the list *widget* itself — so we read its items instead.)
    result = fresh_wallet.client.call("get_list_items", target="vaultDrawer.vaultList")
    assert result.get("ok") is True
    assert result.get("items") == []
