/*
Creates or updates a BusinessAccounts row for an email so admin logs resolve company_name
instead of showing "Unknown".

Usage:
1) Replace values in the DECLARE block.
2) Run the full script as one batch in Azure SQL Query Editor/SSMS.
*/

DECLARE @email NVARCHAR(255) = 'zyadamraa@gmail.com';
DECLARE @company_name NVARCHAR(255) = 'Zyada MRAA Trading';
DECLARE @address NVARCHAR(500) = 'Unknown';
DECLARE @business_type NVARCHAR(100) = 'retail';
DECLARE @billing_method NVARCHAR(50) = 'credit_card';
DECLARE @discount_percent INT = 1;

IF EXISTS (SELECT 1 FROM dbo.BusinessAccounts WHERE email = @email)
BEGIN
    UPDATE dbo.BusinessAccounts
    SET company_name = @company_name,
        address = COALESCE(NULLIF(@address, ''), address),
        business_type = COALESCE(NULLIF(@business_type, ''), business_type),
        billing_method = COALESCE(NULLIF(@billing_method, ''), billing_method),
        discount_percent = @discount_percent
    WHERE email = @email;
END
ELSE
BEGIN
    INSERT INTO dbo.BusinessAccounts
        (company_name, address, business_type, billing_method, discount_percent, email)
    VALUES
        (@company_name, @address, @business_type, @billing_method, @discount_percent, @email);
END

SELECT account_id, company_name, email
FROM dbo.BusinessAccounts
WHERE email = @email;
