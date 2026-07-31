-- PostgreSQL initialization script
-- Creates databases for LangGraph checkpointer and Gitea

CREATE DATABASE gitea;

GRANT ALL PRIVILEGES ON DATABASE langgraph TO triagebot;
GRANT ALL PRIVILEGES ON DATABASE gitea TO triagebot;

SELECT 'PostgreSQL databases initialized successfully' AS status;
