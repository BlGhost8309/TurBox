"""Build collection search requests from a compact JSON configuration."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Sequence


def load_query_templates(path: Path) -> List[Dict[str, Any]]:
    """Load and minimally validate query templates from JSON."""
    if not path.exists():
        raise FileNotFoundError(f"Не найден JSON-конфиг: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    templates = data.get("templates") if isinstance(data, dict) else None
    if not isinstance(templates, list) or not templates:
        raise ValueError("JSON-конфиг должен содержать непустой список 'templates'")

    for index, template in enumerate(templates, start=1):
        if not isinstance(template, dict):
            raise ValueError(f"Шаблон #{index} должен быть JSON-объектом")
        for field in ("cities", "countries"):
            values = template.get(field)
            if not isinstance(values, list) or not values:
                raise ValueError(f"В шаблоне #{index} поле '{field}' должно быть непустым списком")
            if not all(isinstance(value, str) and value.strip() for value in values):
                raise ValueError(f"В шаблоне #{index} поле '{field}' содержит пустое значение")
        for field in ("date_range", "nights", "adults"):
            if not str(template.get(field, "")).strip():
                raise ValueError(f"В шаблоне #{index} не заполнено поле '{field}'")

    return templates


def generate_query_groups(templates: Sequence[Dict[str, Any]]) -> List[List[str]]:
    """Generate one city x country Cartesian product for every template."""
    groups: List[List[str]] = []

    for template in templates:
        date_range = str(template["date_range"]).strip()
        nights = str(template["nights"]).strip()
        adults = str(template["adults"]).strip()
        filters_value = template.get("filters", "")
        filters = "" if filters_value is None else str(filters_value).strip()
        queries: List[str] = []

        for city in template["cities"]:
            for country in template["countries"]:
                query = (
                    f"{city.strip()}|{country.strip()}|{date_range}"
                    f"|ночей:{nights}|взрослых:{adults}"
                )
                if filters:
                    query += f"|{filters}"
                queries.append(query)

        groups.append(queries)

    return groups


def render_search_config(existing_text: str, query_groups: Sequence[Sequence[str]]) -> str:
    """Replace only the ЗАПРОСЫ section and preserve the parameters above it."""
    lines = existing_text.splitlines()
    requests_index = next(
        (index for index, line in enumerate(lines) if line.strip().upper() == "ЗАПРОСЫ"),
        None,
    )

    if requests_index is None:
        prefix = ["ПАРАМЕТРЫ", "searchMinPriceData=true", "", "ЗАПРОСЫ"]
    else:
        prefix = lines[: requests_index + 1]

    while prefix and not prefix[-1].strip():
        prefix.pop()

    output = prefix + [""]
    for index, group in enumerate(query_groups):
        output.extend(group)
        if index < len(query_groups) - 1:
            output.append("")

    return "\n".join(output).rstrip() + "\n"


def update_search_config(json_path: Path, output_path: Path) -> int:
    """Generate requests and atomically update the working search config."""
    templates = load_query_templates(json_path)
    groups = generate_query_groups(templates)
    existing_text = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
    rendered = render_search_config(existing_text, groups)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_path.write_text(rendered, encoding="utf-8")
    temporary_path.replace(output_path)

    return sum(len(group) for group in groups)
