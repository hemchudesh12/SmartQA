"""
automation/tests/test_search.py — Tests for Product Search module.

Module: products (search route)
Route tested: /search?q=...
Markers: smoke, regression

Test inventory (4 tests):
  Smoke:      test_search_existing_product
  Regression: test_search_no_results, test_search_empty_query,
              test_search_partial_name
"""

import pytest

from automation.pages.search_page import SearchPage


@pytest.mark.smoke
def test_search_existing_product(page, base_url):
    """Searching for a known product name returns at least one result."""
    sp = SearchPage(page, base_url)
    sp.search("Headphones")

    assert sp.search_results_container.is_visible(), \
        "Search results container should be visible after a matching search."
    assert sp.result_count() >= 1, \
        "Expected at least one result for 'Headphones'."


@pytest.mark.regression
def test_search_no_results(page, base_url):
    """Searching for a term that matches no products shows the no-results state."""
    sp = SearchPage(page, base_url)
    sp.search("xyznotaproduct123")

    assert sp.no_results.is_visible(), \
        "Expected the no-results element to be visible."
    assert not sp.search_results_container.is_visible(), \
        "Search results container should NOT appear when there are no matches."


@pytest.mark.regression
def test_search_empty_query(page, base_url):
    """Submitting an empty search query shows the empty-query placeholder state."""
    sp = SearchPage(page, base_url)
    sp.search("")   # fills nothing, clicks the button

    assert sp.empty_query_state.is_visible(), \
        "Expected the empty-query placeholder to be visible."
    assert not sp.search_results_container.is_visible(), \
        "No results container should appear for an empty query."


@pytest.mark.regression
def test_search_partial_name(page, base_url):
    """Searching with a partial product name finds matching products."""
    sp = SearchPage(page, base_url)
    sp.search("key")   # "Mechanical Keyboard" contains "key"

    assert sp.search_results_container.is_visible()
    assert sp.result_count() >= 1, \
        "Expected at least 'Mechanical Keyboard' to match partial search 'key'."
