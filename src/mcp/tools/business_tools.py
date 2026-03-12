from typing import Any, Optional, TypedDict

from mcp.services.business_service import (
    create_business_account,
    get_business_by_domain,
)


class CreateBusinessAccountArgs(TypedDict):
    company_name: str
    address: str
    business_type: str
    billing_method: str
    domain: str
    authorized_emails: list[str]


class GetBusinessArgs(TypedDict):
    domain: str


def tool_create_business_account(arguments: CreateBusinessAccountArgs) -> Any:
    return create_business_account(
        company_name=arguments["company_name"],
        address=arguments["address"],
        business_type=arguments["business_type"],
        billing_method=arguments["billing_method"],
        domain=arguments["domain"],
        authorized_emails=arguments["authorized_emails"],
    )


def tool_get_business_by_domain(arguments: GetBusinessArgs) -> Optional[dict[str, Any]]:
    return get_business_by_domain(
        domain=arguments["domain"],
    )
