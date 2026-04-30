import requests
import json
import os
import random
import time
import re
import json_repair

# ========== НАСТРОЙКИ ==========
OLLAMA_API = "http://localhost:11434/api/generate"
MODEL = "command-r:35b-v0.1-q4_K_M"
OUTPUT_DIR = "output"
NAMES_FILE = "names.txt"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Значение имени {name} — тайна, судьба, характер</title>
    <meta name="description" content="Узнайте значение имени {name}, происхождение, характер и совместимость. Тайна имени и астрология.">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #4a0e4e; }}
        .adsense {{ margin: 20px 0; text-align: center; }}
    </style>
</head>
<body>
    <article>
        <h1>Значение имени {name}</h1>

        <h2>Происхождение</h2>
        {origin_html}

        <h2>Характер</h2>
        {character_html}

        <h2>Судьба и карьера</h2>
        {career_html}

        <h2>Совместимость</h2>
        <ul>
            {compatibility_html}
        </ul>

        <h2>Астрология и талисманы</h2>
        {astrology_html}

        <p><em>Статья подготовлена с помощью искусственного интеллекта. Данные носят ознакомительный характер.</em></p>
    </article>
    <div class="adsense">
        <!-- Место под Google AdSense -->
    </div>
    <footer>
        <p>© 2025 Тайна имени. Все права защищены.</p>
    </footer>
</body>
</html>
"""

SYSTEM_PROMPT = """Ты — редактор сайта о значении имён. Твой родной язык — русский. Ты пишешь ТОЛЬКО литературным русским языком, без латиницы, без знаков зодиака в разделе совместимости.
Ты получаешь имя и стиль. Создай **развёрнутую статью** (не менее 200 слов на каждый из трёх основных разделов).
Верни СТРОГО валидный JSON с полями:
{
    "origin": ["абзац1", "абзац2", "абзац3"],
    "character": ["абзац1", "абзац2", "абзац3", "абзац4", "абзац5"],
    "career": ["абзац1", "абзац2", "абзац3"],
    "compatibility": ["Имя1 — причина (1-2 предложения)", "Имя2 — причина", "Имя3 — причина", "Имя4 — причина"],
    "astrology": ["Камень: название", "Цвет: название", "Планета: название", "Стихия: название", "Число удачи: число"]
}
Жёсткие правила:
- Каждый элемент массива — законченный абзац длиной от 50 символов.
- В поле character ключевые черты выделяй префиксом ЖИРНЫЙ: (слитно со словом). Например: «обладает ЖИРНЫЙ:смелостью».
- В совместимости перечисляй ТОЛЬКО ЛИЧНЫЕ ИМЕНА людей (Анна, Дмитрий, Ольга...). Запрещено упоминать знаки зодиака.
- Никаких комментариев, выводи только JSON.
"""

STYLES = [
    "в стиле древних легенд (эпический, с отсылками к мифам)",
    "с научно-популярным уклоном (логичный, с фактами и наблюдениями)",
    "с юмором, но уважительно (лёгкий, ироничный, но не обидный)",
    "в романтическом ореоле (возвышенный, с чувствами и образами)",
    "с упором на психологию (аналитический, с описанием внутреннего мира)"
]

LATIN_REPLACEMENTS = {
    "ancient": "древне", "ale": "але", "exandros": "эксандрос",
    "Zeusa": "Зевса", "ambitious": "амбициозный", "leader": "лидер",
    "romantic": "романтичный", "andros": "андрос", "alexo": "алексо",
}

DEFAULT_DATA = {
    "origin": ["Происхождение имени доподлинно неизвестно, но оно окружено ореолом тайны."],
    "character": ["Характер этого имени соткан из противоречий."],
    "career": ["Судьба и карьера обладателя имени складываются по-разному."],
    "compatibility": ["Совместимость с другими именами изучается астрологами."],
    "astrology": ["Камень:", "Цвет:", "Планета:", "Стихия:", "Число удачи:"]
}

def load_names(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def filter_non_cyrillic(text):
    allowed = re.compile(r'[^а-яА-ЯёЁ0-9\s.,:;!?«»\-]')
    filtered = allowed.sub('', text)
    filtered = re.sub(r' +', ' ', filtered)
    return filtered.strip()

def remove_latin(text):
    for eng, ru in LATIN_REPLACEMENTS.items():
        text = re.sub(r'\b' + re.escape(eng) + r'\b', ru, text, flags=re.IGNORECASE)
    return text

def clean_all_text(text):
    text = remove_latin(text)
    text = filter_non_cyrillic(text)
    return text

def generate_prompt(name, style):
    return f"""Имя: {name}
Стиль: {style}

Создай подробный JSON-ответ."""

def parse_json_response(text):
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1:
        raise ValueError("JSON не найден")
    json_str = text[start:end+1]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        try:
            repaired = json_repair.repair_json(json_str)
            return json.loads(repaired)
        except Exception as e:
            raise ValueError(f"Не удалось починить JSON: {e}")

def boldify(text):
    text = re.sub(r'(ЖИРНЫЙ|ЖИРНОМУ|ЖИРНЫМ|ЖИРНАЯ|ЖИРНОЕ|ЖИРНЫЕ):?\s+(\w+)',
                  r'<strong>\2</strong>', text, flags=re.IGNORECASE)
    text = re.sub(r'(ЖИРНЫЙ|ЖИРНОМУ|ЖИРНЫМ|ЖИРНАЯ|ЖИРНОЕ|ЖИРНЫЕ):', r'<strong>', text, flags=re.IGNORECASE)
    return text

def merge_fragmented_paragraphs(html):
    html = re.sub(r'</p>\s*<p>', ' ', html)
    html = re.sub(r' {2,}', ' ', html)
    return html

def fix_broken_tags(html):
    html = re.sub(r':</strong>', '</strong>:', html)
    html = re.sub(r'<strong>:\s*</strong>', '', html)
    html = re.sub(r'<strong>\s*</strong>', '', html)
    html = re.sub(r'<strong>(\w+)</strong>\s+<strong>', r'<strong>\1 ', html)
    return html

def final_cleanup(html):
    html = merge_fragmented_paragraphs(html)
    html = fix_broken_tags(html)
    html = re.sub(r' {2,}', ' ', html)
    html = '\n'.join(line for line in html.splitlines() if line.strip())
    return html

def build_html(name, data):
    for key in DEFAULT_DATA:
        if key not in data or not isinstance(data[key], list):
            data[key] = DEFAULT_DATA[key]
        data[key] = [str(item) for item in data[key]]

    for key in data:
        data[key] = [clean_all_text(item) for item in data[key]]

    origin_html = '\n'.join(f'<p>{p}</p>' for p in data['origin'])
    character_html = '\n'.join(f'<p>{boldify(p)}</p>' for p in data['character'])
    career_html = '\n'.join(f'<p>{p}</p>' for p in data['career'])

    compats = [f'<li>{item}</li>' for item in data['compatibility']]
    compatibility_html = '\n'.join(compats)

    astrology_html = '\n'.join(f'<p>{item}</p>' for item in data['astrology'])

    html = HTML_TEMPLATE.format(
        name=name,
        origin_html=origin_html,
        character_html=character_html,
        career_html=career_html,
        compatibility_html=compatibility_html,
        astrology_html=astrology_html
    )
    return final_cleanup(html)

def generate_article(name, style):
    prompt = generate_prompt(name, style)
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0.8,
            "top_p": 0.95,
            "repeat_penalty": 1.15,
            "num_predict": 3000
        }
    }
    response = requests.post(OLLAMA_API, json=payload)
    if response.status_code == 200:
        data = response.json()
        raw = data["response"].strip()
        for attempt in range(2):
            try:
                parsed = parse_json_response(raw)
                return build_html(name, parsed)
            except (json.JSONDecodeError, ValueError) as e:
                print(f"  Попытка {attempt+1}: ошибка парсинга JSON ({e})")
                if attempt == 0:
                    response = requests.post(OLLAMA_API, json=payload)
                    if response.status_code == 200:
                        raw = response.json()["response"].strip()
                    else:
                        raise Exception("Повторный запрос не удался")
        print("  Внимание: используется шаблон по умолчанию.")
        return build_html(name, {})
    else:
        raise Exception(f"API error: {response.status_code} {response.text}")

def sanitize_filename(name):
    name = name.lower().replace(" ", "-")
    return "".join(c for c in name if c.isalnum() or c in "-").strip("-")

def save_article(name, content):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = sanitize_filename(name) + ".html"
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath

def main():
    names = load_names(NAMES_FILE)
    print(f"Загружено {len(names)} имён.")

    index_file = "last_index.txt"
    start = 0
    if os.path.exists(index_file):
        with open(index_file, "r") as f:
            start = int(f.read().strip())

    if start >= len(names):
        print("Все имена обработаны. Для перезапуска удалите last_index.txt.")
        return

    count_per_run = 5
    batch = names[start:start+count_per_run]

    for name in batch:
        style = random.choice(STYLES)
        print(f"Генерация: {name} ({style})")
        try:
            content = generate_article(name, style)
            path = save_article(name, content)
            print(f"  -> Сохранено: {path}")
        except Exception as e:
            print(f"  Ошибка: {e}")
        time.sleep(3)

    new_start = min(start + count_per_run, len(names))
    with open(index_file, "w") as f:
        f.write(str(new_start))
    print(f"Готово. Следующий старт с индекса {new_start}.")

if __name__ == "__main__":
    main()