"""Test configuration for the URL shortener application."""

import os

# Test configuration
SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
SQLALCHEMY_TRACK_MODIFICATIONS = False
TESTING = True
