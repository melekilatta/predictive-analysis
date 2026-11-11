#!/usr/bin/env python3
"""Скачивает данные о землетрясениях из открытого USGS API в один CSV-файл.

Регистрация, ключ API и библиотеки не нужны. Скрипт не выполняет кластеризацию
и не изменяет поля, которые вернул USGS.

Пример:
    python download_usgs_earthquakes_csv.py --days 365 --min-magnitude 4.0

Результат по умолчанию: earthquakes_usgs.csv
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Скачать открытые данные USGS Earthquake Catalog в CSV без кластеризации."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Сколько последних дней загрузить (по умолчанию: 365).",
    )
    parser.add_argument(
        "--min-magnitude",
        type=float,
        default=4.0,
        help="Минимальная магнитуда события (по умолчанию: 4.0).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20000,
        help="Максимальное число строк от API, максимум 20000 (по умолчанию: 20000).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("earthquakes_usgs.csv"),
        help="Путь к итоговому CSV (по умолчанию: earthquakes_usgs.csv).",
    )
    args = parser.parse_args()

    if not 1 <= args.days <= 3650:
        parser.error("--days должен быть в диапазоне 1–3650.")
    if not -2 <= args.min_magnitude <= 10:
        parser.error("--min-magnitude должен быть числом от -2 до 10.")
    if not 1 <= args.limit <= 20000:
        parser.error("--limit должен быть в диапазоне 1–20000.")
    return args


def build_url(days: int, min_magnitude: float, limit: int) -> str:
    """Формирует запрос к USGS, сразу запрашивая официальный CSV-формат."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    params = {
        "format": "csv",
        "eventtype": "earthquake",
        "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "endtime": end.strftime("%Y-%m-%dT%H:%M:%S"),
        "minmagnitude": min_magnitude,
        "orderby": "time-asc",
        "limit": limit,
    }
    return f"{API_URL}?{urlencode(params)}"


def download_csv(url: str, output: Path) -> int:
    """Сохраняет ответ API атомарно и возвращает число строк с событиями."""
    request = Request(url, headers={"User-Agent": "usgs-csv-downloader/1.0"})
    try:
        with urlopen(request, timeout=90) as response:
            content = response.read()
    except HTTPError as exc:
        raise RuntimeError(f"USGS API вернул HTTP {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"Не удалось подключиться к USGS API: {exc.reason}") from exc

    if not content.startswith(b"time,"):
        preview = content[:160].decode("utf-8", errors="replace").replace("\n", " ")
        raise RuntimeError(f"Вместо ожидаемого CSV API вернул другой ответ: {preview!r}")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output.with_suffix(output.suffix + ".part")
    temporary_output.write_bytes(content)
    temporary_output.replace(output)
    return max(0, content.count(b"\n") - 1)


def main() -> int:
    args = parse_args()
    url = build_url(args.days, args.min_magnitude, args.limit)
    print("Скачиваю CSV из открытого USGS Earthquake Catalog API…")
    try:
        count = download_csv(url, args.output)
    except RuntimeError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1

    print(f"Сохранено событий: {count:,}")
    print(f"CSV: {args.output.resolve()}")
    if count >= args.limit:
        print(
            "Внимание: достигнут limit API. Сократите период, увеличьте порог магнитуды "
            "или загружайте интервалы по отдельности, чтобы не получить усечённые данные.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
