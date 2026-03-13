import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from dotenv import load_dotenv
from supabase import create_client, Client
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Initialize database engine
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL must be set in environment variables")

db_engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Create router
router = APIRouter(prefix="/api", tags=["Attachments"])


@router.post("/attachments/upload")
async def upload_attachment(
    file: UploadFile = File(...),
    session_id: int = Query(..., description="Session ID for the attachment")
):
    """
    Upload file to Supabase Storage and record in conversation_attachments table.
    
    Args:
        file: The file to upload
        session_id: Session ID for tracking the attachment
    
    Returns:
        JSON with status and storage path
    """
    try:
        # Read file content
        file_content = await file.read()
        
        # Define storage path with unique filename
        bucket_name = "conversation-attachments"
        file_ext = os.path.splitext(file.filename)[1]  # Get file extension
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        storage_path = f"{session_id}/{unique_filename}"
        
        # Upload to Supabase Storage
        response = supabase.storage.from_(bucket_name).upload(
            path=storage_path,
            file=file_content,
            file_options={"content-type": file.content_type}
        )
        
        # Check if upload was successful
        if hasattr(response, 'error') and response.error:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload file: {response.error}"
            )
        
        # Insert record into conversation_attachments table
        attachment_id = str(uuid.uuid4())
        
        with db_engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO conversation_attachments 
                    (id, session_id, file_type, source, storage_path, status)
                    VALUES (:id, :session_id, :file_type, :source, :storage_path, :status)
                """),
                {
                    "id": attachment_id,
                    "session_id": session_id,
                    "file_type": "image",
                    "source": "whatsapp",
                    "storage_path": storage_path,
                    "status": "uploaded"
                }
            )
            conn.commit()
        
        return {
            "status": "uploaded",
            "path": storage_path
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )
