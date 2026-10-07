from product_catalog import PRODUCT_METADATA
from model_contracts import PRODUCTS, CANONICAL_SLUGS


def test_every_canonical_product_has_commercial_metadata():
    assert set(PRODUCT_METADATA) == set(CANONICAL_SLUGS)
    for slug in CANONICAL_SLUGS:
        meta = PRODUCT_METADATA[slug]
        assert meta["name"]
        assert meta["family"]
        assert meta["description"]
        assert meta["stage"] in {"engineering", "visual_qa", "production"}
        assert meta["visual_source"] in {"studio_asset", "generated_preview"}


def test_production_release_is_explicit_and_visual_asset_backed():
    production = [slug for slug, meta in PRODUCT_METADATA.items() if meta["stage"] == "production"]
    engineering = [slug for slug, meta in PRODUCT_METADATA.items() if meta["stage"] == "engineering"]

    assert len(production) == 72
    assert len(engineering) == 0

    for slug in production:
        meta = PRODUCT_METADATA[slug]
        assert meta["marketing_image"], slug
        assert meta["marketing_image"].startswith((
            "/images/products/professional/",
            "/images/products/premium-v1/",
        )), slug
        assert meta["visual_source"] == "studio_asset"
        assert PRODUCTS[slug]["stage"] == "production"
        assert PRODUCTS[slug]["version"] == "1.0.0"

    for slug in engineering:
        assert PRODUCTS[slug]["stage"] == "engineering"

    premium = [
        slug for slug in production
        if PRODUCT_METADATA[slug]["marketing_image"].startswith("/images/products/premium-v1/")
    ]
    assert len(premium) == 54


def test_catalog_contracts_keep_builder_and_release_metadata_separate():
    for slug, contract in PRODUCTS.items():
        assert contract["builder"], slug
        assert contract["default"], slug
        assert contract["variant"], slug
        assert contract["stage"] == PRODUCT_METADATA[slug]["stage"]
