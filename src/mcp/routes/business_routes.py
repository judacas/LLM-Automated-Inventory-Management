from typing import Any, Dict, cast

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mcp.services.business_service import (
    create_business_account,
    get_business_by_domain,
)

router = APIRouter(prefix="/business", tags=["Business"])


class CreateBusinessRequest(BaseModel):
    company_name: str
    address: str
    business_type: str
    billing_method: str
    domain: str
    authorized_emails: list[str]


@router.post("/")
def create_business(request: CreateBusinessRequest) -> Dict[str, int]:
    try:
        account_id = create_business_account(
            company_name=request.company_name,
            address=request.address,
            business_type=request.business_type,
            billing_method=request.billing_method,
            domain=request.domain,
            authorized_emails=request.authorized_emails,
        )
        return {"account_id": account_id}
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err)) from err


@router.get("/{domain}")
def get_business(domain: str) -> Dict[str, Any]:
    business = get_business_by_domain(domain)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found.")

    return cast(Dict[str, Any], business)
