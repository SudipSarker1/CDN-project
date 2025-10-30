# Demo Runbook (Draft)

## 1) Start replicas (one per port)
# hypercorn replicas.replica:app --bind 0.0.0.0:9001 --certfile cert/server.crt --keyfile cert/server.key --h2

## 2) Start controller
# hypercorn controller.controller:app --bind 0.0.0.0:8000 --certfile cert/server.crt --keyfile cert/server.key --h2

## 3) Start frontend (optional gateway)
# hypercorn frontend.app:app --bind 0.0.0.0:3000

## 4) Seed replicas from origin
# python origin/origin.py

## 5) Test
# Browser: http://localhost:3000  or curl the controller directly
