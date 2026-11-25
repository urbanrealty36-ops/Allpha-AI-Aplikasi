"""Authenticated media API foundation backed by canonical content_media."""
from __future__ import annotations
import os, uuid
from typing import Any
import httpx
from fastapi import APIRouter, Depends, HTTPException
from allpha_api.auth import current_user
router = APIRouter(prefix="/v1/media", tags=["media"])
def _config():
    base=os.getenv("SUPABASE_URL","").rstrip("/")
    key=os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY")
    if not base or not key:
        raise HTTPException(503,detail={"code":"MEDIA_DB_NOT_CONFIGURED","message":"Media database is not configured."})
    return base,key
@router.get("/{media_id}")
async def get_media(media_id:uuid.UUID,user:dict[str,Any]=Depends(current_user)):
    base,key=_config()
    async with httpx.AsyncClient(timeout=12,trust_env=False,follow_redirects=False) as client:
        response=await client.get(f"{base}/rest/v1/content_media",params={"select":"id,owner_id,status,storage_provider,provider_public_id,provider_resource_type,provider_format,provider_asset_id","id":f"eq.{media_id}","owner_id":f"eq.{user['id']}","limit":"1"},headers={"apikey":key,"Authorization":f"Bearer {key}"})
    if response.status_code>=300:
        raise HTTPException(503,detail={"code":"MEDIA_DB_UNAVAILABLE","message":"Media status unavailable."})
    rows=response.json()
    if not rows:
        raise HTTPException(404,detail={"code":"MEDIA_NOT_FOUND","message":"Media not found."})
    return {"item":rows[0]}
