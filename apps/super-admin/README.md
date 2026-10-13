# Allpha Super Admin

Independent operations and governance application boundary.

- Owns operator-facing screens, not a second copy of business engines.
- All reads and mutations use the backend API and its explicit operator permissions.
- Can be deployed separately from the end-user client.
- Keep environment configuration and deployment independent so this directory can later become its own repository.

Initial implementation step: connect operator session, service health, asset catalog, and user/tenant operations to real backend endpoints.
