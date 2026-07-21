## Code Generation Constraints

- Tech stack: Java Spring Boot / AKSO framework (backend), Vue 3 + Spark (frontend)
- Directory structure: follow existing project module layout, no new modules
- Naming: class PascalCase, method camelCase, constants UPPER_SNAKE_CASE
- No new dependencies (unless dev-plan.md explicitly requires)
- SQL follows T-SQL conventions in `{SKILL_DIR}/references/sql-syntax-guide.md`
- All database operations use parameterized queries, no string concatenation for SQL
