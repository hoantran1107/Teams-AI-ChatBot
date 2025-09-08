"""
URL Redirect Controller

Handles redirects from short URLs to original URLs for RAG citations.
"""

import logging
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import RedirectResponse

from src.services.rag_services.url_shortening_service import url_shortening_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/redirect", tags=["URL Shortening"])


@router.get("/{short_code}")
async def redirect_short_url(short_code: str):
    """
    Redirect from short URL to original URL
    
    Args:
        short_code: The short code identifying the URL mapping
        
    Returns:
        RedirectResponse to the original URL
        
    Raises:
        HTTPException: If short code is not found
    """
    try:
        # Get original URL from database
        original_url = url_shortening_service.get_original_url(short_code)
        
        if not original_url:
            logger.warning(f"Short code not found: {short_code}")
            raise HTTPException(
                status_code=404, 
                detail=f"Short URL '{short_code}' not found"
            )
        
        logger.info(f"Redirecting short code '{short_code}' to: {original_url}")
        
        # Return redirect response
        return RedirectResponse(
            url=original_url,
            status_code=302  # Temporary redirect
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error redirecting short code '{short_code}': {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error during redirect"
        )


@router.get("/info/{short_code}")
async def get_url_info(short_code: str):
    """
    Get information about a short URL without redirecting
    
    Args:
        short_code: The short code identifying the URL mapping
        
    Returns:
        Dict with URL information
        
    Raises:
        HTTPException: If short code is not found
    """
    try:
        from src.services.postgres.models.tables.rag_sync_db.url_shortening_table import URLShortening
        
        # Get URL mapping from database
        url_mapping = URLShortening.get_by_short_code(short_code)
        
        if not url_mapping:
            raise HTTPException(
                status_code=404,
                detail=f"Short URL '{short_code}' not found"
            )
        
        return {
            "short_code": url_mapping.short_code,
            "original_url": url_mapping.original_url,
            "display_url": url_mapping.display_url,
            "created_at": url_mapping.created_at.isoformat(),
            "last_accessed": url_mapping.last_accessed.isoformat() if url_mapping.last_accessed else None,
            "access_count": url_mapping.access_count
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error getting info for short code '{short_code}': {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error getting URL info"
        )
