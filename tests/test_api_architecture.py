"""Проверки разделения HTTP-слоя и работы с базой данных."""

import ast
import unittest
from pathlib import Path

from fastapi import APIRouter
from fastapi.routing import APIRoute

from backend.api.main import app
from backend.api.routers import auth, courses, frontend, modules, users


class APIArchitectureTests(unittest.TestCase):
    def test_api_does_not_execute_sql_or_open_database_connections(self):
        api_dir = Path(__file__).resolve().parents[1] / "src" / "backend" / "api"
        for path in api_dir.rglob("*.py"):
            with self.subTest(file=path.name):
                tree = ast.parse(path.read_text())
                forbidden = [
                    node.func.attr
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in {"cursor", "execute", "executemany", "connect"}
                ]
                self.assertEqual(forbidden, [], f"Обращение к БД в HTTP-слое: {path}")

    def test_endpoints_are_defined_in_separate_routers(self):
        paths = set()
        count = 0
        for module in (auth, courses, frontend, modules, users):
            self.assertIsInstance(module.router, APIRouter)
            for route in module.router.routes:
                if isinstance(route, APIRoute):
                    self.assertEqual(route.endpoint.__module__, module.__name__)
                    paths.add(route.path)
                    count += 1
        self.assertEqual(count, 6)
        self.assertEqual(paths, set(app.openapi()["paths"]))
