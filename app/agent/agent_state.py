from enum import Enum


class AgentState(str, Enum):
    """
    Enum representing all possible agent states in the invoice generation workflow.
    This serves as the single source of truth for agent state across the backend.
    """
    
    # Initial state - collecting customer and invoice information
    COLLECTING_INFO = "collecting_info"
    
    # Need more information to complete the draft
    NEED_MORE_INFO = "need_more_info"
    
    # Draft has been created and is ready for review
    DRAFT_CREATED = "draft_created"
    
    # Waiting for user confirmation on the draft
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    
    # Invoice has been finalized and generated
    FINALIZED = "finalized"

    # Flow completed successfully
    COMPLETED = "completed"
    
    # Error state - something went wrong
    ERROR = "error"
    
    def __str__(self) -> str:
        """Return the string value of the enum."""
        return self.value
