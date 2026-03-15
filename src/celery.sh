#!/bin/sh

celery -A tasks.tasks:celery worker --loglevel=info