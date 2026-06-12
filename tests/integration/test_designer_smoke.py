"""Smoke test: the designer plugin loads and navigates in an isolated wallet."""
from driver import actions


def test_designer_nav_button_present_after_vault_open(ephemeral_wallet):
    client = ephemeral_wallet.client
    actions.create_vault(client, "dgnrvault", "secretpass")

    # The designer's main nav entry loaded (objectName set in plugin.py).
    count = client.call("count", target="designer.navButton")
    assert count.get("ok") is True
    assert count.get("count", 0) >= 1


def test_open_designer_navigates_to_a_designer_page(ephemeral_wallet):
    client = ephemeral_wallet.client
    actions.create_vault(client, "dgnrvault2", "secretpass")

    page = actions.open_designer(client)
    assert page.get("ok") is True
    assert str(page.get("vault_page", "")).startswith("designer.")
