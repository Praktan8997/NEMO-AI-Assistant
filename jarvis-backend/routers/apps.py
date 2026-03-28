"""
Apps Router — browse/search discovered apps, refresh the index
"""
from fastapi import APIRouter, Query
from agents.app_discovery import get_app_discovery

router = APIRouter(prefix="/api/apps", tags=["Apps"])


@router.get("/search")
async def search_apps(q: str = Query("", description="App name to fuzzy-search")):
    """Fuzzy-search installed apps by name. Returns top matches."""
    discovery = get_app_discovery()
    if not q.strip():
        return {"apps": discovery.list_apps(limit=50), "total": len(discovery._cache)}

    # Do a fuzzy scan over the index and return top 10
    from difflib import SequenceMatcher
    q_norm = q.lower().strip()
    scored = []
    for key in discovery._cache:
        if q_norm in key or key in q_norm:
            scored.append((1.0, key))
        else:
            score = SequenceMatcher(None, q_norm, key).ratio()
            if score >= 0.4:
                scored.append((score, key))
    scored.sort(key=lambda x: -x[0])
    return {"apps": [name for _, name in scored[:10]], "query": q}


@router.post("/refresh")
async def refresh_app_index():
    """Force a full rescan of all installed apps."""
    discovery = get_app_discovery()
    discovery.refresh()
    return {"message": "App index refreshed.", "total": len(discovery._cache)}


@router.get("/count")
async def app_count():
    """Return number of indexed apps."""
    discovery = get_app_discovery()
    return {"total": len(discovery._cache)}
