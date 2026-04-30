/*
  Remove all EmailLogs for one customer and response_eval rows that attach to those logs.

  The dashboard joins dbo.response_evaluations to dbo.EmailLogs on
  customer_email and response_log_id = EmailLogs.id. Only evaluations that match both
  (eval row tied to a log row being removed) are deleted first so quote-only
  evaluation rows keyed by quote_id are left alone unless they share the same IDs.

  If you also want to purge ALL dbo.response_evaluations for this email address
  (including quote-quotebook rows), uncomment the OPTIONAL block below BEFORE the
  join-based delete.

  Run in SSMS / Azure Data Studio against your warehouse database.
*/

SET NOCOUNT ON;

DECLARE @customer_email NVARCHAR(255) = N'kaushik.selvakumar.val@gmail.com';

BEGIN TRANSACTION;

BEGIN TRY
  DECLARE @removed_evals INT;
  DECLARE @removed_logs INT;

  /* OPTIONAL — remove every evaluation row for this address:
  DELETE FROM dbo.response_evaluations WHERE customer_email = @customer_email;
  */

  DELETE re
  FROM dbo.response_evaluations AS re
  INNER JOIN dbo.EmailLogs AS el
    ON el.customer_email = re.customer_email
   AND el.id = re.response_log_id
  WHERE el.customer_email = @customer_email;

  SET @removed_evals = @@ROWCOUNT;

  DELETE FROM dbo.EmailLogs WHERE customer_email = @customer_email;

  SET @removed_logs = @@ROWCOUNT;

  COMMIT TRANSACTION;

  PRINT N'Deleted response_evaluations rows (log-linked): ' + CAST(@removed_evals AS NVARCHAR(20));
  PRINT N'Deleted EmailLogs rows: ' + CAST(@removed_logs AS NVARCHAR(20));
END TRY
BEGIN CATCH
  IF @@TRANCOUNT > 0
    ROLLBACK TRANSACTION;

  DECLARE @msg NVARCHAR(4000) = ERROR_MESSAGE();
  RAISERROR (N'Delete failed: %s', 16, 1, @msg);
END CATCH;
