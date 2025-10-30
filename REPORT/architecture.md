# Architecture (Draft)

## Overview
Origin → Controller → Replicas → (optional) Frontend gateway.

## Components
- Origin: pushes videos to replicas (pre-distribution).
- Replicas: store and stream video (`GET /videos/{id}`).
- Controller: chooses a replica (round-robin) and proxies the stream.
- Frontend: browser entry-point (optional).

## Data Flow
1) Origin uploads files to all replicas.
2) Client requests `/api/videos/{id}` (or calls controller directly).
3) Controller selects a replica and streams back.
