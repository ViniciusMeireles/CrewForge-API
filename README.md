# CrewForge — Accounts and Teams Management :rocket:

API service for managing accounts, teams, and permissions with comprehensive 
organizational hierarchy support.

<img width="2560" height="1080" alt="CrewForge API" src="https://github.com/user-attachments/assets/d07500c8-cea4-41e4-a6e6-74c12fd43792" />

## Table of Contents
- [Overview](#overview-open_book)
- [Key Features](#key-features-sparkles)
- [API Architecture](#api-architecture-building_construction)
  - [Core Resources](#core-resources-package)
  - [Authentication Flow](#authentication-flow-closed_lock_with_key)
  - [Role Hierarchy](#role-hierarchy-crown)
  - [Endpoint Structure](#endpoint-structure-satellite)
    - [Accounts Module](#accounts-module-busts_in_silhouette)
    - [Teams Module](#teams-module-jigsaw)
    - [Authentication Module](#authentication-module-key)
- [Stack](#stack-hammer_and_wrench)
- [Installation](#installation-inbox_tray)
- [Usage](#usage-computer)
- [API Documentation](#api-documentation-books)
- [Security Features](#security-features-shield)
- [Contributing](#contributing-handshake)
- [License](#license-page_facing_up)
- [Contact](#contact-telephone_receiver)


## Overview :open_book:
CrewForge is a robust RESTful API service designed to handle complex organizational 
structures, team management, and user permissions. It provides a complete solution for 
managing organizations, teams, members, and invitations with role-based access control 
and secure authentication mechanisms.


## Key Features :sparkles:
- :office: **Organizational Management**: Create and manage multiple organizations with unique slugs and ownership.
- :busts_in_silhouette: **Member Management**: Manage user memberships across organizations and teams with granular role assignments.
- :jigsaw: **Team Hierarchy**: Build nested team structures within organizations with custom roles and permissions.
- :incoming_envelope: **Invitation System**: Secure invitation workflow with expiration controls and role-based invitations.
- :closed_lock_with_key: **Authentication**: JWT-based authentication with refresh token support and password reset functionality.
- :crown: **Role-Based Access Control**: Four-tier role system (Owner, Admin, Manager, Member) with hierarchical permissions.
- :mag: **Comprehensive Filtering**: Advanced query parameter support for searching and filtering across all resources.
- :file_folder: **File Storage**: Secure file upload and download with role-based access control.
- :books: **Comprehensive API Documentation**: Auto-generated Swagger documentation for easy API exploration and testing.


## API Architecture :building_construction:

### Core Resources :package:
- :office: **Organization**: Represents a company or group with unique attributes and ownership.
- :bust_in_silhouette: **Member**: Represents a user associated with an organization, including their role and status.
- :jigsaw: **Team**: Represents a group within an organization, supporting nested structures and custom roles.
- :incoming_envelope: **Invitation**: Represents an invitation sent to a user to join an organization or team with specific roles.
- :link: **Team Members**: Represents the association between members and teams, including their roles within the team.
- :file_folder: **StoredFile**: Represents a file stored in the system with access permissions based on ownership and organization roles.

### Authentication Flow :closed_lock_with_key:
User login must be performed in **3 steps**:

1. Obtain JWT tokens via `/api/auth/token/` using username/password credentials.
2. List the organizations available to the authenticated user via `/api/accounts/organizations/`.
3. Select which organization will be used for the active session via `/api/accounts/organizations/{id}/login/`.

Important: obtaining a JWT token alone does **not** fully complete the login flow for organization-scoped operations. The user must also select the organization context in step 3.

Additional authentication-related actions:

4. Use the access token for authenticated requests (Bearer authentication).
5. Refresh expired access tokens via `/api/auth/token/refresh/`.
6. Reset passwords using `/api/auth/password/reset/` and `/api/auth/password/reset/confirm/`.


### Role Hierarchy :crown:
- :crown: **Owner**: Full access to all resources and settings within the organization.
- :gear: **Admin**: Manage members, teams, and invitations but cannot delete the organization.
- :hammer_and_wrench: **Manager**: Manage teams and members within teams but cannot manage the organization or invitations.
- :bust_in_silhouette: **Member**: Basic access to organization resources without management capabilities.


### Endpoint Structure :satellite:
#### Accounts Module :busts_in_silhouette:
- :incoming_envelope: `/api/accounts/invitations/` - Invitation management.
- :file_folder: `/api/accounts/stored-files/` - File management (upload, list, retrieve, update, delete).
- :file_folder: `/api/accounts/stored-files/{uuid}/file/` - Download a stored file (supports `?download=true` for attachment).
- :bust_in_silhouette: `/api/accounts/members/` - Organization member management.
- :office: `/api/accounts/organizations/` - Organization CRUD operations.
- :closed_lock_with_key: `/api/accounts/organizations/{id}/login/` - Organization login to define session context.
- :memo: `/api/accounts/signup/` - User registration with organization creation.

#### Teams Module :jigsaw:
- :jigsaw: `/api/teams/teams/` -  Team management within organizations.
- :link: `/api/teams/team-members/` - Team membership management.

#### Authentication Module :key:
- :closed_lock_with_key: `/api/auth/token/` - JWT token obtainment.
- :arrows_counterclockwise: `/api/auth/token/refresh/` - Refresh JWT access tokens.
- :white_check_mark: `/api/auth/token/verify/` - Token validation.
- :e-mail: `/api/auth/password/reset/` - Initiate password reset.
- :lock: `/api/auth/password/reset/confirm/` - Confirm password reset.


## Stack :hammer_and_wrench:
- :package: **Packaging**: [UV](https://docs.astral.sh/uv/)
- :snake: **Backend**: [Django](https://www.djangoproject.com/), [Django REST Framework](https://www.django-rest-framework.org/), [Django Filter](https://django-filter.readthedocs.io/)
- :lock: **Authentication**: [Simple JWT](https://django-rest-framework-simplejwt.readthedocs.io/)
- :file_cabinet: **Database**: [PostgreSQL](https://www.postgresql.org/)
- :whale: **Containerization**: [Docker](https://docs.docker.com/), [Docker Compose](https://docs.docker.com/compose/)
- :books: **API Documentation**: [Swagger](https://swagger.io/) ([drf-spectacular](https://drf-spectacular.readthedocs.io/), [RapiDoc](https://rapidocweb.com/))
- :dash: **WSGI Server**: [Gunicorn](https://gunicorn.org/)
- :test_tube: **Testing**: [pytest](https://pytest-django.readthedocs.io/), [Factory Boy](https://factoryboy.readthedocs.io/)
- :blue_book: **Linting & Formatting**: [Ruff](https://docs.astral.sh/ruff/)


## Installation :inbox_tray:
1. Clone the repository:
   ```bash
   git clone https://github.com/ViniciusMeireles/CrewForge.git
    ```
   
2. Navigate to the project directory:
   ```bash
   cd CrewForge
    ```

3. Copy the example environment file and configure it:
   ```bash
   cp example.env .env
    ```

4. Build and start the Docker containers:
   ```bash
   docker compose build --no-cache
    ``` 
    ```bash
    docker compose up -d
     ```
   
5. Run database migrations:
   ```bash
   docker compose exec django_api uv run python manage.py migrate
    ```
   
6. (Optional) Create a superuser for admin access:
    ```bash
    docker compose exec django_api uv run python manage.py createsuperuser
   ```
   
7. Access the application:
   - :globe_with_meridians: API: `http://localhost:8000/api/schema/swagger-ui/`
   - :gear: Admin Panel: `http://localhost:8000/admin/`


## Usage :computer:
- The Swagger UI for API documentation is available at `http://localhost:8000/api/schema/swagger-ui/`.
- The admin panel is accessible at `http://localhost:8000/admin/`.
- Use the superuser credentials created during installation to log in to the admin panel.
- Refer to the API documentation for available endpoints and usage instructions.
- To start the application, run:
    ```bash
   docker compose up -d
    ```
- To stop the application, run:
    ```bash
   docker compose down
    ```
- To view logs, run:
    ```bash
   docker compose logs -f
    ```
- To rebuild the containers, run:
    ```bash
   docker compose build --no-cache
    ```
- To see all available Makefile commands, run:
    ```bash
   make help
    ```
   

## API Documentation :books:
Interactive API documentation is available at `http://localhost:8000/api/schema/swagger-ui/` providing:

- Complete endpoint documentation with parameters and schemas.
- Interactive testing capabilities.
- Request/response examples.
- Authentication support for testing secured endpoints.


## Design Patterns :blue_book:
CrewForge follows established design patterns for maintainability and extensibility. Documentation is available in the `docs/` directory:

- [Structural Patterns](./docs/structural-patterns.md) - Mixin, Abstract Model, and Module patterns
- [Behavioral Patterns](./docs/behavioral-patterns.md) - Template Method, Strategy, and Validation patterns
- [Creational Patterns](./docs/creational-patterns.md) - Factory Method and Builder patterns
- [Architectural Patterns](./docs/architectural-patterns.md) - Layered Architecture, Facade, and Test Infrastructure


## Security Features :shield:
- :closed_lock_with_key: JWT-based authentication with access and refresh tokens.
- :lock: Password reset functionality with secure token handling.
- :crown: Role-based access control with hierarchical permissions.
- :alarm_clock: Invitation expiration controls.
- :file_folder: File-based access control with role-based permissions (Owner, Owners Organization, Admins Organization, Managers Organization, Members Organization, Public).
- :e-mail: Secure password reset workflow.
- :globe_with_meridians: CORS protection configured for production environments.


## Contributing :handshake:
Contributions are welcome! Please follow these steps:
1. Fork the repository.
2. Create a new branch for your feature or bugfix.
3. Commit your changes with clear messages.
4. Ensure your code adheres to the project's coding standards and passes all tests.
5. Push your changes to your forked repository.
6. Open a pull request to the main repository.
7. Describe your changes and the problem they solve in the pull request description.


## License :page_facing_up:
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.


## Contact :telephone_receiver:
For questions or support, please contact [Vinicius Meireles](https://github.com/ViniciusMeireles/).


##
CrewForge provides a comprehensive foundation for building applications requiring sophisticated organizational 
structures, team management, and permission systems with enterprise-grade security and scalability. :rocket:
