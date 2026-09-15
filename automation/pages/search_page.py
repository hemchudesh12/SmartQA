"""
automation/pages/search_page.py — Page Object for /search.
"""

from playwright.sync_api import Locator

from automation.pages.base_page import BasePage


class SearchPage(BasePage):
    URL = "/search"

    # ------------------------------------------------------------------
    # Locators
    # ------------------------------------------------------------------

    @property
    def search_input(self) -> Locator:
        return self.page.get_by_test_id("search-input")

    @property
    def search_button(self) -> Locator:
        return self.page.get_by_test_id("search-button")

    @property
    def search_results_container(self) -> Locator:
        return self.page.get_by_test_id("search-results")

    @property
    def no_results(self) -> Locator:
        return self.page.get_by_test_id("search-no-results")

    @property
    def empty_query_state(self) -> Locator:
        return self.page.get_by_test_id("search-empty-query")

    @property
    def query_label(self) -> Locator:
        return self.page.get_by_test_id("search-query-label")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def search(self, query: str) -> None:
        """Navigate to search page, enter query, and submit."""
        self.navigate()
        self.search_input.fill(query)
        self.search_button.click()
        self.page.wait_for_load_state("networkidle")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def result_cards(self) -> Locator:
        """All product cards within the search results container."""
        return self.search_results_container.locator(".product-card")

    def result_count(self) -> int:
        """Returns the number of product result cards shown."""
        if not self.search_results_container.is_visible():
            return 0
        return self.result_cards().count()
