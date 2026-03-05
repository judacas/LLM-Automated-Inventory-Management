from enum import Enum


class AdminIntent(str, Enum):
    CHECK_INVENTORY = "check_inventory"
    CHECK_QUOTES = "check_quotes"
    SYSTEM_SUMMARY = "system_summary"
    UNKNOWN = "unknown"


class AdminIntentClassifier:
    """Classify what an admin is asking for."""

    def classify(self, message: str) -> AdminIntent:
        text = message.lower()

        # inventory-ish
        if any(
            word in text for word in ["inventory", "stock", "restock", "availability"]
        ):
            return AdminIntent.CHECK_INVENTORY

        # quote-ish
        if any(word in text for word in ["quote", "quotes", "pricing", "price"]):
            return AdminIntent.CHECK_QUOTES

        # summary-ish
        if any(
            word in text
            for word in ["summary", "status", "dashboard", "overview", "system"]
        ):
            return AdminIntent.SYSTEM_SUMMARY

        return AdminIntent.UNKNOWN
