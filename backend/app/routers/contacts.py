from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import or_

from ..database import get_db
from ..models import Contact
from ..schemas import ContactsPage, ContactOut

router = APIRouter()


@router.get("/contacts", response_model=ContactsPage)
def search_contacts(
    q: str = Query(default="", description="Busca por nome ou número"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    db: DBSession = Depends(get_db),
):
    query = db.query(Contact)

    if q:
        search = f"%{q}%"
        query = query.filter(
            or_(
                Contact.phone.ilike(search),
                Contact.name.ilike(search),
            )
        )

    total = query.count()
    items = (
        query.order_by(Contact.last_seen_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return ContactsPage(
        total=total,
        page=page,
        page_size=page_size,
        items=[ContactOut.from_orm(c) for c in items],
    )
