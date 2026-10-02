from model_contracts import PRODUCTS


def test_every_product_exposes_default_and_variant_contract():
    assert len(PRODUCTS) == 72
    for slug, contract in PRODUCTS.items():
        assert contract.get("default"), slug
        assert contract.get("variant"), slug
        assert contract["variant"] != contract["default"], slug
