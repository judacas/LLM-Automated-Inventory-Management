/*
  Remove one customer (primary BusinessAccounts.email match) and related rows.
  Change @email below, then run the whole script, OR copy each DELETE block one at a time.

  Skips Purchase* / AuthorizedEmails / EmailLogs if the table does not exist.
  Identity columns: you do NOT need to reseed after DELETE — next INSERT just gets the next number (with gaps), which is normal.
*/

SET NOCOUNT ON;

DECLARE @email NVARCHAR(255) = N'kaushik.selvakumar.val@gmail.com';
DECLARE @norm NVARCHAR(255) = LOWER(LTRIM(RTRIM(@email)));

IF OBJECT_ID('tempdb..#P', 'U') IS NOT NULL DROP TABLE #P;
SELECT account_id INTO #P FROM dbo.BusinessAccounts WHERE LOWER(LTRIM(RTRIM(email))) = @norm;

BEGIN TRANSACTION;

BEGIN TRY
  /* Evaluations: by customer email, or by quote ids for primary account */
  DELETE FROM dbo.response_evaluations
  WHERE LOWER(LTRIM(RTRIM(ISNULL(customer_email, N'')))) = @norm
     OR response_log_id IN (SELECT q.quote_id FROM dbo.Quotes AS q INNER JOIN #P AS p ON q.account_id = p.account_id);

  IF OBJECT_ID('dbo.EmailLogs', 'U') IS NOT NULL
    DELETE FROM dbo.response_evaluations
    WHERE response_log_id IN (
      SELECT el.id FROM dbo.EmailLogs AS el WHERE LOWER(LTRIM(RTRIM(el.customer_email))) = @norm
    );

  IF OBJECT_ID('dbo.PurchaseOrderItems', 'U') IS NOT NULL AND OBJECT_ID('dbo.PurchaseOrders', 'U') IS NOT NULL
    DELETE poi FROM dbo.PurchaseOrderItems AS poi
    INNER JOIN dbo.PurchaseOrders AS po ON po.purchase_order_id = poi.purchase_order_id
    INNER JOIN #P AS p ON po.account_id = p.account_id;

  IF OBJECT_ID('dbo.PurchaseOrders', 'U') IS NOT NULL
    DELETE po FROM dbo.PurchaseOrders AS po INNER JOIN #P AS p ON po.account_id = p.account_id;

  DELETE qi FROM dbo.QuoteItems AS qi
  INNER JOIN dbo.Quotes AS q ON q.quote_id = qi.quote_id INNER JOIN #P AS p ON q.account_id = p.account_id;

  DELETE q FROM dbo.Quotes AS q INNER JOIN #P AS p ON q.account_id = p.account_id;

  IF OBJECT_ID('dbo.EmailLogs', 'U') IS NOT NULL
    DELETE FROM dbo.EmailLogs WHERE LOWER(LTRIM(RTRIM(customer_email))) = @norm;

  IF OBJECT_ID('dbo.AuthorizedEmails', 'U') IS NOT NULL
    DELETE FROM dbo.AuthorizedEmails WHERE LOWER(LTRIM(RTRIM(email))) = @norm;

  DELETE ba FROM dbo.BusinessAccounts AS ba INNER JOIN #P AS p ON ba.account_id = p.account_id;

  COMMIT TRANSACTION;
END TRY
BEGIN CATCH
  IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
  THROW;
END CATCH;

DROP TABLE #P;
