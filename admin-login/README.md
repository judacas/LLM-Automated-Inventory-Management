## Admin Login (USF Capstone – Microsoft Project #1)

## DOCUMENTATION

This project implements the Admin Login for the Contoso Inventory Management System as part of the USF Capstone – Microsoft Project #1.

## FEATURES

    1. Login API implemented (POST /auth/login) with hard-coded admin credentials (temporary, per project guidance)

    2. Protected dashboard (GET /admin/dashboard) requiring authentication via JWT

    3. Cookie-based authentication with a 1-hour expiry

    4. Dashboard displays:

            => Outstanding Quotes

            => Outstanding Total (formatted with $ for currency)

            => Unavailable Items Requested

            => Buttons for "View All Quotes" and "View Inventory"

    5. Winston logging implemented for:

            => Login attempts (success/failure)

            => Dashboard access

            => Logout events

## RUNNING LOCALLY

Terminal: Git Bash (or any terminal)

    1. Navigate to the project folder (e.g., adminLogin)

    2. Install dependencies: npm install & npm winston

    3. Start the server: npm start

    4. Open your browser and go to http://localhost:3000

    6. Use the hard-coded admin credentials to log in

## NOTES

    -> The node_modules folder and logs folder are included in .gitignore and should not be pushed to GitHub.

    -> The dashboard’s "Outstanding Total" is formatted with a dollar sign; unavailable items and quotes are displayed as numbers.

    -> JWT tokens are stored in cookies (HTTP-only) and expire after 1 hour.

    -> Logs are written to logs/ using Winston.