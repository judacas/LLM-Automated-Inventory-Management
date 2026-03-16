from database_tools.services.business_service import (
    BusinessAccount,
    create_business_account,
    get_business_by_domain,
)


def tool_create_business_account(
    company_name: str,
    address: str,
    business_type: str,
    billing_method: str,
    domain: str,
    authorized_emails: list[str],
) -> int:
    return create_business_account(
        company_name=company_name,
        address=address,
        business_type=business_type,
        billing_method=billing_method,
        domain=domain,
        authorized_emails=authorized_emails,
    )


def tool_get_business_by_domain(domain: str) -> BusinessAccount | None:
    return get_business_by_domain(domain=domain)