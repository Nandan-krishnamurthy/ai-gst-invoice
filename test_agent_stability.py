"""
Test suite to verify agent stability - all code paths return valid AgentResponse.

This test ensures:
1. No code path returns None
2. All responses have valid AgentState enums (not strings)
3. Handle different message types without errors
"""

import sys
import logging
from sqlalchemy.orm import Session
from datetime import datetime, timezone

# Setup Python path
sys.path.insert(0, "c:\\GST-MCP-invoice")

from app.agent.schemas import AgentResponse
from app.agent.agent_state import AgentState
from app.agent import agent_service
from app.db.database import get_db, engine
from app.db.models import Base

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize database
Base.metadata.create_all(bind=engine)

def get_test_db() -> Session:
    """Get a test database session."""
    return next(get_db())


def test_response_is_valid(response: Any, test_name: str) -> bool:
    """
    Validate that response is a proper AgentResponse and not None.
    
    Returns:
        True if response is valid, False otherwise
    """
    if response is None:
        logger.error(f"FAIL [{test_name}]: Response is None!")
        return False
    
    if not isinstance(response, AgentResponse):
        logger.error(f"FAIL [{test_name}]: Response is not AgentResponse, got {type(response)}")
        return False
    
    # Check that agent_state is an AgentState enum, not a string
    if isinstance(response.agent_state, str):
        # This is actually okay since AgentState is a string enum
        # But let's verify it's a valid state
        try:
            AgentState(response.agent_state)
            logger.debug(f"OK [{test_name}]: Valid AgentState enum value: {response.agent_state}")
        except ValueError:
            logger.error(f"FAIL [{test_name}]: Invalid agent_state string: {response.agent_state}")
            return False
    elif isinstance(response.agent_state, AgentState):
        logger.debug(f"OK [{test_name}]: Valid AgentState: {response.agent_state.value}")
    else:
        logger.error(f"FAIL [{test_name}]: agent_state has unexpected type: {type(response.agent_state)}")
        return False
    
    # Check that message is not empty
    if not response.message:
        logger.error(f"FAIL [{test_name}]: Message is empty!")
        return False
    
    logger.info(f"PASS [{test_name}]: {response.message[:80]}")
    return True


def run_test(message: str, session_id: str = "test-session", test_name: str = None) -> bool:
    """Run a single test case."""
    if test_name is None:
        test_name = message[:40]
    
    try:
        db = get_test_db()
        response = agent_service.handle_message(
            session_id=session_id,
            message=message,
            db=db
        )
        db.commit()
        return test_response_is_valid(response, test_name)
    except Exception as e:
        logger.error(f"FAIL [{test_name}]: Exception: {e}", exc_info=True)
        return False
    finally:
        db.close()


def main():
    """Run all stability tests."""
    logger.info("=" * 80)
    logger.info("AGENT STABILITY TEST SUITE")
    logger.info("=" * 80)
    
    test_cases = [
        # Test case: Confirm/accept messages
        ("confirm", "test-session-1", "confirm message"),
        ("accept", "test-session-2", "accept message"),
        ("yes", "test-session-3", "yes message"),
        
        # Test case: Create invoice (standalone)
        ("create invoice", "test-session-4", "create invoice standalone"),
        ("create invoice for Acme Corp", "test-session-5", "create invoice with buyer name"),
        
        # Test case: Seller/buyer details
        ("buyer name: John Doe", "test-session-6", "buyer name update"),
        ("seller state: California", "test-session-7", "seller state update"),
        ("buyer gstin: 29AABUJ5055K2Z0", "test-session-8", "buyer gstin update"),
        
        # Test case: Add items
        ("add 5 laptops at 50000", "test-session-9", "add item simple"),
        ("add 2 desks at 15000 gst 18", "test-session-10", "add item with gst"),
        
        # Test case: GST updates
        ("gst 18", "test-session-11", "gst rate update"),
        
        # Test case: HSN codes
        ("hsn code is 8471", "test-session-12", "hsn code update"),
        
        # Test case: Finalize
        ("finalize", "test-session-13", "finalize invoice"),
        
        # Test case: Unrecognized messages (should trigger LLM fallback)
        ("hello", "test-session-14", "unrecognized message"),
        ("what can you do?", "test-session-15", "capability question"),
        
        # Test case: Ambiguous messages (should trigger LLM extraction)
        ("I need an invoice", "test-session-16", "implicit message"),
    ]
    
    passed = 0
    failed = 0
    
    for message, session_id, test_name in test_cases:
        logger.info(f"\nRunning: {test_name}")
        if run_test(message, session_id, test_name):
            passed += 1
        else:
            failed += 1
    
    logger.info("\n" + "=" * 80)
    logger.info(f"TEST RESULTS: {passed} passed, {failed} failed out of {passed + failed} tests")
    logger.info("=" * 80)
    
    if failed == 0:
        logger.info("SUCCESS: All tests passed! Agent is stable.")
        return 0
    else:
        logger.error(f"FAILURE: {failed} tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
