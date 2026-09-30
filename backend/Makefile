.PHONY: db-upgrade db-downgrade db-current db-history db-revision

db-upgrade:
	alembic upgrade head

db-downgrade:
	alembic downgrade -1

db-current:
	alembic current

db-history:
	alembic history --verbose

db-revision:
	@test -n "$(m)" || (echo 'Usage: make db-revision m="describe change"' && exit 1)
	alembic revision -m "$(m)"
