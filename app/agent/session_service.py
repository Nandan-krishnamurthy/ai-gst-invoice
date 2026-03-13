from typing import Optional
import uuid
from sqlalchemy.orm import Session
from app.db.models import AgentSession


def get_or_create_session(session_id: Optional[str] = None, db: Session = None) -> str:
    """
    Get or create an agent session.
    
    Args:
        session_id: Optional session ID. If provided, returns it. If not, generates a new UUID.
        db: Database session. If not provided, creates a new one.
    
    Returns:
        Session ID string
    """
    # Generate new session ID if not provided
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # Check if session exists
    existing_session = db.query(AgentSession).filter(AgentSession.session_id == session_id).first()
    
    # If not exists, create new session
    if not existing_session:
        new_session = AgentSession(session_id=session_id)
        db.add(new_session)
        db.flush()
    
    return session_id


def set_active_draft(session_id: str, draft_id: str, db: Session = None) -> None:
    """
    Set the active draft ID for a session.
    
    Args:
        session_id: Session ID
        draft_id: Draft ID to set as active
        db: Database session. If not provided, creates a new one.
    """
    session = db.query(AgentSession).filter(AgentSession.session_id == session_id).first()
    if session:
        session.active_draft_id = draft_id
        db.flush()


def get_active_draft(session_id: str, db: Session = None) -> Optional[str]:
    """
    Get the active draft ID for a session.
    
    Args:
        session_id: Session ID
        db: Database session. If not provided, creates a new one.
    
    Returns:
        Active draft ID if present, None otherwise
    """
    session = db.query(AgentSession).filter(AgentSession.session_id == session_id).first()
    return session.active_draft_id if session else None


def clear_active_draft(session_id: str, db: Session = None) -> None:
    """
    Clear the active draft ID for a session.
    
    Args:
        session_id: Session ID
        db: Database session. If not provided, creates a new one.
    """
    session = db.query(AgentSession).filter(AgentSession.session_id == session_id).first()
    if session:
        session.active_draft_id = None
        db.flush()
