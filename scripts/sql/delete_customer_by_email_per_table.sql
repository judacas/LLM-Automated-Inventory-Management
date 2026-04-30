/*
  One customer (email on BusinessAccounts).

  Azure Portal Query editor: variables and #temp tables only exist in the SAME batch/run.
  If you highlight and run ONLY "section 2", you get: Must declare the scalar variable "@norm".

  Fix — either:
    A) Select from SETUP through the section you want (include lines below DECLARE … through that DELETE), then Run, or
    B) Use the "standalone" snippet under section 2 (no variables).

  Replace the email in SETUP (or in standalone snippets). If your PO table is singular
  dbo.PurchaseOrder, change sections 3–4 accordingly.
*/

/* ========== SETUP (include this in the same run as any step that uses @norm or #P) ========== */
DECLARE @email NVARCHAR(255) = N'kaushik.selvakumar.val@gmail.com';
DECLARE @norm NVARCHAR(255) = LOWER(LTRIM(RTRIM(@email)));

IF OBJECT_ID('tempdb..#P', 'U') IS NOT NULL DROP TABLE #P;
SELECT account_id INTO #P FROM dbo.BusinessAccounts WHERE LOWER(LTRIM(RTRIM(email))) = @norm;
/* Optional: SELECT * FROM #P;  -- verify account_id(s) */


/* ========== 1 — response_evaluations (by email + quotes for #P) ========== */
DELETE FROM dbo.response_evaluations
WHERE LOWER(LTRIM(RTRIM(ISNULL(customer_email, N'')))) = @norm
   OR response_log_id IN (
        SELECT q.quote_id FROM dbo.Quotes AS q INNER JOIN #P AS p ON q.account_id = p.account_id
      );


/* ========== 2 — response_evaluations (log ids for this email, if EmailLogs exists) ========== */
/* Requires SETUP in the same execute batch as this block. */
IF OBJECT_ID('dbo.EmailLogs', 'U') IS NOT NULL
  DELETE FROM dbo.response_evaluations
  WHERE response_log_id IN (
    SELECT el.id FROM dbo.EmailLogs AS el WHERE LOWER(LTRIM(RTRIM(el.customer_email))) = @norm
  );

/* ----- 2b — SAME as section 2, but runnable alone (no @norm): edit the literal email ----- */
/*
IF OBJECT_ID('dbo.EmailLogs', 'U') IS NOT NULL
  DELETE FROM dbo.response_evaluations
  WHERE response_log_id IN (
    SELECT el.id FROM dbo.EmailLogs AS el
    WHERE LOWER(LTRIM(RTRIM(el.customer_email))) = LOWER(LTRIM(N'kaushik.selvakumar.val@gmail.com'))
  );
*/


/* ========== 3 — PurchaseOrderItems (only for POs on #P accounts) ========== */
IF OBJECT_ID('dbo.PurchaseOrderItems', 'U') IS NOT NULL AND OBJECT_ID('dbo.PurchaseOrders', 'U') IS NOT NULL
  DELETE poi
  FROM dbo.PurchaseOrderItems AS poi
  INNER JOIN dbo.PurchaseOrders AS po ON po.purchase_order_id = poi.purchase_order_id
  INNER JOIN #P AS p ON po.account_id = p.account_id;


/* ========== 4 — PurchaseOrders (#P accounts only) ========== */
IF OBJECT_ID('dbo.PurchaseOrders', 'U') IS NOT NULL
  DELETE po FROM dbo.PurchaseOrders AS po INNER JOIN #P AS p ON po.account_id = p.account_id;
/* If your table is singular: dbo.PurchaseOrder — change the name above. */


/* ========== 5 — QuoteItems (quotes belonging to #P) ========== */
DELETE qi
FROM dbo.QuoteItems AS qi
INNER JOIN dbo.Quotes AS q ON q.quote_id = qi.quote_id
INNER JOIN #P AS p ON q.account_id = p.account_id;


/* ========== 6 — Quotes (#P accounts only) ========== */
DELETE q FROM dbo.Quotes AS q INNER JOIN #P AS p ON q.account_id = p.account_id;


/* ========== 7 — EmailLogs (this customer email only) ========== */
IF OBJECT_ID('dbo.EmailLogs', 'U') IS NOT NULL
  DELETE FROM dbo.EmailLogs WHERE LOWER(LTRIM(RTRIM(customer_email))) = @norm;


/* ========== 8 — AuthorizedEmails (this address only) ========== */
IF OBJECT_ID('dbo.AuthorizedEmails', 'U') IS NOT NULL
  DELETE FROM dbo.AuthorizedEmails WHERE LOWER(LTRIM(RTRIM(email))) = @norm;


/* ========== 9 — BusinessAccounts (primary row for this email) ========== */
DELETE ba FROM dbo.BusinessAccounts AS ba INNER JOIN #P AS p ON ba.account_id = p.account_id;


/* ========== CLEANUP ========== */
DROP TABLE #P;
