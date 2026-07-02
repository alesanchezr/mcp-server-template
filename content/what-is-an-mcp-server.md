---
title: What is an MCP Server?
---

**MCP** stands for **Model Context Protocol** — an open standard that lets AI applications connect to external tools, data, and services in a consistent way.

## The idea

Instead of every AI app building its own integrations, MCP defines a common protocol. A **server** exposes capabilities (tools, resources, prompts), and a **client** (like Cursor or Claude Desktop) connects to it and uses those capabilities on your behalf.

Think of it like USB for AI: one plug, many devices.

## What does an MCP server do?

An MCP server can expose things like:

- **Tools** — actions the AI can call (search a database, send an email, run a command)
- **Resources** — read-only data the AI can fetch (files, docs, API responses)
- **Prompts** — reusable prompt templates

The AI client discovers what's available, calls tools when needed, and reads resources for context.

## Why it matters

MCP makes integrations reusable. Write one server, and any MCP-compatible client can use it — no custom plugin per app.

This blog itself is built with FastAPI and is set up to add a FastMCP layer later, so AI agents could interact with the blog programmatically.
