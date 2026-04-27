from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from opentelemetry import trace
from pydantic import BaseModel

from mcp.services.business_service import (
    create_business_account,
    get_business_by_domain,
)

router = APIRouter(prefix="/business", tags=["Business"])
tracer = trace.get_tracer(__name__)


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
        span = trace.get_current_span()
        span.set_attribute("company_name", request.company_name)
        span.set_attribute("workflow_type", "business_onboarding")
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
    span = trace.get_current_span()
    span.set_attribute("domain", domain)
    span.set_attribute("workflow_type", "business_lookup")
    business = get_business_by_domain(domain)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found.")

    return business
