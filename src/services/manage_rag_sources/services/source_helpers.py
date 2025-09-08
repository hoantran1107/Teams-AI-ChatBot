from typing import List, Dict, Any
from src.services.manage_rag_sources.services.manage_source import ManageSource

async def get_available_sources(user_id = None) -> list:
    """Get all available RAG sources using direct service call.
    
    Returns:
        list: A list of dictionaries, each containing 'id' and 'name' of a source.
    """
    try:
        # Get common sources
        common_sources = ManageSource.get_common_source_names()
        sources_list = []
        
        # Process common sources
        if common_sources and isinstance(common_sources, list):
            for source in common_sources:
                sources_list.append({"id": source.id, "name": source.name})
        
        # Get user-specific sources if user_id is provided
        if user_id:
            user_sources = ManageSource.get_source_name_by_user_id(user_id=user_id)
            if user_sources and isinstance(user_sources, list):
                for source in user_sources:
                    sources_list.append({"id": source.id, "name": source.name})
        
        return sources_list
    except Exception as e:
        print(f"Error fetching sources: {str(e)}")
        return []

async def get_source_by_id(source_id: str) -> Dict[str, Any]:
    """Get source information by its ID.
    
    Args:
        source_id: The ID of the source to look up
        
    Returns:
        dict: A dictionary containing the source information with 'id' and 'name'
    """
    try:
        # Get all sources (could be optimized in the future to directly query by ID)
        all_sources = await get_available_sources()
        
        # Find the source with matching ID
        for source in all_sources:
            if source["id"] == source_id:
                return source
                
        # Return None if no matching source was found
        return None
    except Exception as e:
        print(f"Error getting source by ID: {str(e)}")
        return None