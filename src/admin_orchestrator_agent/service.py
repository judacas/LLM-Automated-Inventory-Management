from admin_orchestrator_agent.classifier import AdminIntent, AdminIntentClassifier
from inventory_agent.repository import InventoryRepository
from inventory_agent.service import InventoryService


class AdminOrchestratorService:
    """
    Routes admin requests to the correct underlying tool/agent.

    Today:
    - inventory path uses InventoryService (mock repo)
    - quote path is a stub (your teammate will own it)
    """

    def __init__(self) -> None:
        self.classifier = AdminIntentClassifier()
        self.inventory_service = InventoryService(InventoryRepository())

    def handle_message(self, message: str) -> str:
        intent = self.classifier.classify(message)

        if intent == AdminIntent.CHECK_INVENTORY:
            # Placeholder: just show one SKU for now
            item = self.inventory_service.get_item_availability("SKU-1")
            return f"Inventory check: SKU-1 has {item.quantity} units ({item.status})."

        if intent == AdminIntent.CHECK_QUOTES:
            return "Delegating to Quote Agent (not implemented in my module)."

        if intent == AdminIntent.SYSTEM_SUMMARY:
            # Later: call both quote agent + inventory agent, combine results
            return "System summary: inventory + quotes (summary not implemented yet)."

        return "I’m not sure what you mean. Can you clarify what you want to check?"
