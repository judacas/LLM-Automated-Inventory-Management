/*
  Clears:
    - All EmailLogs except rows for the protected email
    - All Quotes / QuoteItems / PurchaseOrders / PurchaseOrderItems except for that customer's account(s)
    - response_evaluations rows that are NOT tied to that customer (by email, quote, or email log)

  Protected customer: kaushik.selvakumar@gmail.com (must exist as BusinessAccounts.email).

  Run in SSMS / Azure Data Studio. Review, then execute. Uses one transaction.
*/

SET NOCOUNT ON;

DECLARE @keep_email NVARCHAR(255) = N'kaushik.selvakumar@gmail.com';
DECLARE @keep NVARCHAR(255) = LOWER(LTRIM(RTRIM(@keep_email)));

IF OBJECT_ID('tempdb..#KeepAccounts', 'U') IS NOT NULL DROP TABLE #KeepAccounts;
CREATE TABLE #KeepAccounts (account_id INT NOT NULL PRIMARY KEY);
INSERT INTO #KeepAccounts (account_id)
SELECT account_id
FROM dbo.BusinessAccounts
WHERE LOWER(LTRIM(RTRIM(email))) = @keep;

IF NOT EXISTS (SELECT 1 FROM #KeepAccounts)
BEGIN
  RAISERROR(N'Protected email not found on dbo.BusinessAccounts — aborting so nothing is mass-deleted.', 16, 1);
  RETURN;
END;

BEGIN TRANSACTION;

BEGIN TRY
  /* 1 — Evaluations: drop anything not clearly owned by the protected customer */
  DELETE re
  FROM dbo.response_evaluations AS re
  WHERE NOT (
      (re.customer_email IS NOT NULL AND LOWER(LTRIM(RTRIM(re.customer_email))) = @keep)
      OR EXISTS (
        SELECT 1
        FROM dbo.Quotes AS q
        INNER JOIN #KeepAccounts AS k ON k.account_id = q.account_id
        WHERE q.quote_id = re.response_log_id
      )
      OR (
        OBJECT_ID('dbo.EmailLogs', 'U') IS NOT NULL
        AND EXISTS (
          SELECT 1
          FROM dbo.EmailLogs AS el
          WHERE el.id = re.response_log_id
            AND LOWER(LTRIM(RTRIM(el.customer_email))) = @keep
        )
      )
    );

  /* 2 — Purchase order lines & orders (non–protected accounts only) */
  IF OBJECT_ID('dbo.PurchaseOrderItems', 'U') IS NOT NULL AND OBJECT_ID('dbo.PurchaseOrders', 'U') IS NOT NULL
  BEGIN
    DELETE poi
    FROM dbo.PurchaseOrderItems AS poi
    INNER JOIN dbo.PurchaseOrders AS po ON po.purchase_order_id = poi.purchase_order_id
    WHERE po.account_id NOT IN (SELECT account_id FROM #KeepAccounts);
  END

  IF OBJECT_ID('dbo.PurchaseOrders', 'U') IS NOT NULL
    DELETE po FROM dbo.PurchaseOrders AS po WHERE po.account_id NOT IN (SELECT account_id FROM #KeepAccounts);

  /* 3 — Quotes (non–protected accounts) */
  DELETE qi
  FROM dbo.QuoteItems AS qi
  INNER JOIN dbo.Quotes AS q ON q.quote_id = qi.quote_id
  WHERE q.account_id NOT IN (SELECT account_id FROM #KeepAccounts);

  DELETE q FROM dbo.Quotes AS q WHERE q.account_id NOT IN (SELECT account_id FROM #KeepAccounts);

  /* 4 — Email logs (everything except protected address) */
  IF OBJECT_ID('dbo.EmailLogs', 'U') IS NOT NULL
    DELETE FROM dbo.EmailLogs WHERE LOWER(LTRIM(RTRIM(ISNULL(customer_email, N'')))) <> @keep;

  COMMIT TRANSACTION;
END TRY
BEGIN CATCH
  IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
  THROW;
END CATCH;

DROP TABLE #KeepAccounts;
