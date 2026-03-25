"""
Aegis Backend — Incidents API

Retrieval and management endpoints for Incidents.
"""

from __future__ import annotations

from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Incident, Comment
from app.schemas import DataResponse, ResponseMeta

router = APIRouter()

@router.get("/incidents", response_model=DataResponse)
async def list_incidents(request: Request, db: AsyncSession = Depends(get_db)) -> Any:
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    result = await db.execute(select(Incident).order_by(Incident.created_at.desc()).limit(100))
    incidents = result.scalars().all()
    
    data = []
    for inc in incidents:
        data.append({
            "id": str(inc.id),
            "title": inc.title,
            "description": inc.description,
            "severity": inc.severity.value,
            "status": inc.status.value,
            "category": inc.category,
            "reporterName": inc.reporter_name,
            "createdAt": inc.created_at.isoformat(),
            "updatedAt": inc.updated_at.isoformat(),
            "rcaSummary": getattr(inc, "rca_summary", None),
            "probableCause": getattr(inc, "probable_cause", None),
        })
        
    return DataResponse(
        data=data,
        meta=ResponseMeta(request_id=req_id),
        message="Retrieved incidents successfully."
    )


@router.get("/incidents/{incident_id}/comments", response_model=DataResponse)
async def list_comments(incident_id: int, request: Request, db: AsyncSession = Depends(get_db)) -> Any:
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    result = await db.execute(
        select(Comment)
        .where(Comment.incident_id == incident_id)
        .order_by(Comment.created_at.asc())
    )
    comments = result.scalars().all()
    
    data = [
        {
            "id": str(c.id),
            "text": c.text,
            "authorName": c.author_name,
            "createdAt": c.created_at.isoformat(),
        }
        for c in comments
    ]
        
    return DataResponse(
        data=data,
        meta=ResponseMeta(request_id=req_id),
        message="Retrieved comments successfully."
    )


@router.post("/incidents/{incident_id}/comments", response_model=DataResponse)
async def create_comment(incident_id: int, payload: dict, request: Request, db: AsyncSession = Depends(get_db)) -> Any:
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    text = payload.get("text")
    author_name = payload.get("authorName", "Anonymous")
    
    if not text:
        raise HTTPException(status_code=422, detail="Text is required")
        
    comment = Comment(
        incident_id=incident_id,
        text=text,
        author_uid="system",
        author_name=author_name
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    
    return DataResponse(
        data={
            "id": str(comment.id),
            "text": comment.text,
            "authorName": comment.author_name,
            "createdAt": comment.created_at.isoformat(),
        },
        meta=ResponseMeta(request_id=req_id),
        message="Comment added."
    )
