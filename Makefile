# Makefile for Django App

# Define variables
PYTHON = python
DJANGO_MANAGE = python manage.py

# Run the development server
run:
	$(DJANGO_MANAGE) runserver 0.0.0.0:8000

# Create a new Django superuser
createsuperuser:
	$(DJANGO_MANAGE) createsuperuser

# Run database migrations
migrate:
	$(DJANGO_MANAGE) makemigrations
	$(DJANGO_MANAGE) migrate

.PHONY: run createsuperuser migrate createapp test rungateway cleanpyc