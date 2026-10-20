# Expense Tracker — Smart Personal Finance Management

**A secure, multi-user expense tracking application designed to help people understand their spending, plan purchases, manage budgets, and make better financial decisions.**

> **Project Status:** 🚧 Active Development  
> **Current Stage:** Foundational Django development, database integration, and project setup.

## Overview

Expense Tracker is a web application in development that aims to make personal financial management simpler, more organized, and more accessible.

The goal is to help users record everyday expenses, organize purchases into categories, compare planned spending with actual costs, and monitor their financial activities through a clear, responsive dashboard.

The application is being designed with privacy and security in mind from the beginning. Each registered user will have access to their own financial records, with appropriate permissions preventing users from viewing or modifying another user's private information.

The project will be developed incrementally, beginning with the core expense management functionality and expanding into budgeting, reporting, notifications, and intelligent financial insights.

## Project Objectives

- Provide a simple way to record and manage everyday expenses.
- Help users organize transactions by category and date.
- Support shopping plans with estimated and actual prices.
- Help users create budgets and monitor their spending.
- Present spending patterns through clear summaries and visual reports.
- Protect private financial records through user authentication and authorization.
- Deliver a responsive experience across desktop, tablet, and mobile devices.
- Establish a reliable foundation for production deployment and real-world user testing.

## Planned Features

### 1. User Accounts and Security
- User registration, login, and logout.
- Private financial records for each account.
- User-level permissions for viewing, editing, and deleting records.
- Secure handling of application configuration and database credentials.

### 2. Expense Management
- Record purchases and everyday expenses.
- Store item descriptions, quantities, unit prices, dates, and categories.
- Calculate expense totals.
- Edit and delete existing expense records.

### 3. Shopping Planner
- Create shopping lists before making purchases.
- Record estimated prices for planned items.
- Update items with their actual purchase prices.
- Compare estimated and actual spending.
- Connect completed purchases to expense records where appropriate.

### 4. Budget Management
- Create overall or category-specific budgets.
- Track spending against budget limits.
- Display remaining budgets and spending progress.
- Provide alerts when spending approaches or exceeds configured limits.

### 5. Dashboard and Reports
- Display spending summaries.
- Show expenses by category and time period.
- Compare planned expenditure with actual expenditure.
- Present financial information through charts and visual indicators.

### 6. Future Enhancements
- Customizable spending alerts and notifications.
- More advanced financial reports.
- Intelligent spending insights and personalized suggestions.
- Additional usability, accessibility, and performance improvements.

*These are planned capabilities. Features will be marked as implemented as development progresses.*

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application programming language |
| Django | Backend web framework |
| Django Templates | Server-rendered user interface |
| Tailwind CSS | Planned responsive styling and UI design |
| PostgreSQL | Relational database |
| Neon | Hosted PostgreSQL database service used during development |
| Git and GitHub | Version control and source-code collaboration |
| Visual Studio Code | Development environment |

The application is being developed with a preference for clear architecture, maintainable code, secure data access, and incremental testing.

## Development Progress

The project is currently in its foundational development phase.

### Work completed so far

- [x] Created the GitHub repository for the project.
- [x] Cloned the repository to the local development environment.
- [x] Established the initial Django project workspace.
- [x] Started working with Django views and HTML templates.
- [x] Practiced connecting Django/Python to a PostgreSQL database hosted on Neon.
- [x] Experimented with database queries and retrieving records for display in a web application.
- [x] Began organizing repository files and configuring Git ignore rules for local and sensitive files.

### Current development priorities

- [ ] Finalize the project directory structure.
- [ ] Establish the core Django application architecture.
- [ ] Configure the database through Django's model and migration system.
- [ ] Implement a custom user model before the first application migrations.
- [ ] Build secure registration, login, and logout functionality.
- [ ] Implement expense and category management.
- [ ] Add shopping lists and estimated-versus-actual price comparisons.
- [ ] Implement budgets and financial summaries.
- [ ] Add automated tests, including tests for user-data isolation.
- [ ] Integrate the responsive interface using Tailwind CSS.
- [ ] Configure production settings and deploy a testable version.

## Project Architecture

The application is planned to use a modular Django structure. The following is the intended direction, not a claim that every component has already been created.

```text
Expense-Tracker-project/
│
├── README.md
├── .gitignore
│
└── portfolio/
    ├── manage.py
    ├── project_config/
    ├── Expense_app/
    ├── templates/
    ├── static/
    ├── .env.example
    └── requirements.txt
```

The actual Django project and application package names may differ as the structure is finalized.

As the application grows, functionality will be separated into logical Django apps, such as:

- `accounts` — user accounts and authentication.
- `expenses` — expense records and categories.
- `shopping` — shopping lists and price comparisons.
- `budgets` — budget limits and spending progress.
- `dashboard` — summaries, reports, and visual insights.

The final structure will be documented as these components are implemented.

## Database Design Principles

The database will use PostgreSQL and Django's ORM for most application data operations.

The intended design principles include:

- Use appropriate primary keys and foreign-key relationships.
- Associate private financial records with their owning user.
- Store monetary values using decimal-based database fields rather than floating-point numbers.
- Use migrations to manage schema changes.
- Validate data before saving it.
- Apply ownership checks when users access or modify records.
- Test that one user cannot access another user's private records.

The database schema will evolve as the application's requirements become more concrete.

## Local Development

### Prerequisites

Before running the application, ensure that you have:

- Python installed.
- Git installed.
- Access to a PostgreSQL database.
- The project repository cloned to your computer.

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd Expense-Tracker-project
```

Replace the placeholder with the actual URL of your GitHub repository.

### 2. Enter the Django project directory

```bash
cd portfolio
```

This reflects the current repository structure, where the Django project is inside the `portfolio` directory.

### 3. Create and activate a virtual environment

On Windows PowerShell:

```powershell
python -m venv env
.\env\Scripts\Activate.ps1
```

If your terminal is Git Bash:

```bash
python -m venv env
source env/Scripts/activate
```

### 4. Install dependencies

If a `requirements.txt` file is available:

```bash
python -m pip install -r requirements.txt
```

If dependency management has not yet been finalized, install the project's required packages according to its current configuration.

### 5. Configure environment variables

Create a local `.env` file using the project's expected environment-variable names.

For example, if the application is configured to read `DATABASE_URL`:

```dotenv
DATABASE_URL=your_postgresql_connection_string
```

Add other required settings according to the Django configuration.

**Security:** Never commit `.env` files, database passwords, secret keys, recovery codes, or other credentials to GitHub. Use a sanitized `.env.example` file to document required configuration without exposing real secrets.

### 6. Apply database migrations

Once the Django database settings and models are configured:

```bash
python manage.py migrate
```

### 7. Start the development server

```bash
python manage.py runserver
```

Open the local development address shown in the terminal, normally:

`http://127.0.0.1:8000/`

These are the intended setup steps; successful execution depends on the current project configuration, installed dependencies, database connection, and implemented routes.

## Security and Privacy

Because this application handles financial information, security is a core development requirement.

The project will prioritize:

- Django's built-in authentication and password-handling mechanisms.
- Secure session and CSRF protection.
- Server-side validation of submitted data.
- User-specific database queries and authorization checks.
- Safe handling of environment variables and credentials.
- Production-appropriate `DEBUG`, host, cookie, and HTTPS settings.
- Automated tests for authentication, permissions, and data isolation.
- Database backups and a documented recovery strategy before production use.

The application will not be considered production-ready until its security configuration, data access rules, error handling, and deployment settings have been reviewed and tested.

## Testing and Quality Assurance

Testing will be introduced alongside implementation rather than postponed until the end.

Planned checks include:

- User registration and authentication.
- Creating, editing, and deleting expenses.
- Correct calculations for quantities, prices, and totals.
- Shopping estimates compared with actual costs.
- Budget calculations and spending thresholds.
- Access restrictions between different user accounts.
- Form validation and error handling.
- Responsive behavior across common screen sizes.
- Production configuration and deployment checks.

## Production Deployment Roadmap

The goal is to deploy a publicly accessible test version so that real users can try the application and provide feedback.

The deployment process will include:

1. Finalize the core application structure.
2. Confirm dependencies and database migrations.
3. Configure environment variables and production settings.
4. Deploy the Django application to a suitable hosting platform.
5. Connect the production application to a properly secured PostgreSQL database.
6. Configure static files, HTTPS, allowed hosts, and application logging.
7. Run smoke tests and verify user-data isolation.
8. Share the test URL with selected users.
9. Collect feedback, fix issues, and iterate.

A public URL will be added to this README once deployment has been completed and verified.

## Contributing and Feedback

This project is under active development. Suggestions, bug reports, usability feedback, and improvement ideas are welcome.

When reporting an issue, please include:

- A clear description of the problem.
- Steps to reproduce it.
- The expected behavior.
- The actual behavior.
- Relevant screenshots or error messages, with passwords, tokens, and personal information removed.

Please do not publish real financial records, database credentials, or other sensitive information in issue reports.

## Project Vision

Expense Tracker aims to grow from a foundational Django application into a dependable personal finance tool that helps users understand their spending, plan purchases, and make more informed financial decisions.

The development approach is incremental: build the fundamentals correctly, protect users' data, test important workflows, and introduce additional features based on real user needs.

---

**Project:** Expense Tracker  
**Status:** In development  
**Backend:** Python and Django  
**Database:** PostgreSQL  
**Repository:** This GitHub repository

*The feature list and architecture describe the current direction of development. Documentation will be updated as features are implemented and verified.*