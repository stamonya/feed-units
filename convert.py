#!/usr/bin/env python3
"""Profitbase XML -> лёгкий JSON для Тильды.

FEED_URL берётся из переменной окружения (секрет репозитория).
Результат: docs/units.json
"""
import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

FEED_URL = os.environ["FEED_URL"]
OUT = os.environ.get("OUT", "docs/units.json")
ONLY_STATUS = {"AVAILABLE"}  # какие статусы показывать на сайте


def strip_ns(root):
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def txt(el, path, default=""):
    node = el.find(path)
    return (node.text or "").strip() if node is not None and node.text else default


def num(s):
    try:
        return float(s.replace(",", "."))
    except (ValueError, AttributeError):
        return None


def custom(el):
    """custom-field -> {имя: значение} (только непустые)."""
    out = {}
    for cf in el.findall("custom-field"):
        name = txt(cf, "name")
        val = txt(cf, "value")
        if name and val:
            out[name] = val
    return out


def main():
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    root = strip_ns(ET.fromstring(data))

    units = []
    for o in root.findall("offer"):
        status = txt(o, "status")
        if status not in ONLY_STATUS:
            continue

        cf = custom(o)
        price = num(txt(o, "price/value"))
        # если есть акция с ценой — показываем её, иначе базовую
        for so in o.findall("special-offers/special-offer"):
            dp = num(txt(so, "discount-price"))
            if dp and (price is None or dp < price):
                price = dp
        area = num(txt(o, "area/value"))

        plan = plan_floor = ""
        for img in o.findall("image"):
            t = img.get("type", "")
            if t == "plan" and not plan:
                plan = (img.text or "").strip()
            elif t == "plan floor" and not plan_floor:
                plan_floor = (img.text or "").strip()

        units.append({
            "id": o.get("internal-id"),
            "number": txt(o, "number"),
            "house": txt(o, "house/name"),
            "house_id": txt(o, "house/id"),
            "section": txt(o, "building-section"),
            "floor": txt(o, "floor"),
            "area": area,
            "price": price,
            "price_m2": round(price / area) if price and area else None,
            "plan": plan,
            "plan_floor": plan_floor,
            "ready": txt(o, "house/building-state") == "hand-over",
            "ready_year": txt(o, "house/built-year"),
            "ready_quarter": txt(o, "house/ready-quarter"),
            "finish": cf.get("Отделка", ""),
            "ceiling": cf.get("Высота потолка", "").replace(",", "."),
            "entrance": cf.get("Вход", ""),
            "keys_today": cf.get("Ключи сегодня", "").lower() == "да",
            "address": txt(o, "object/location/address"),
        })

    units.sort(key=lambda u: (u["house"], u["section"], u["number"]))

    # защита: пустой/сломанный фид не должен затирать рабочий JSON
    if len(units) < 1:
        print("Фид пустой — JSON не обновляю", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({
            "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "count": len(units),
            "units": units,
        }, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK: {len(units)} помещений -> {OUT}")


if __name__ == "__main__":
    main()
