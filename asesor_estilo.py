import re
import json
import html
import asyncio
from typing import List, Dict
import google.generativeai as genai
from nicegui import ui, app

ADVISOR_CSS = """
<style>
  .advisor-shell { max-width: 760px; margin: 0 auto; padding: 24px 16px; }
  .advisor-title {
    font-family: 'Cormorant Garamond', serif;
    color: var(--ink-deep);
    letter-spacing: 0.02em;
  }
  .advisor-sub {
    font-family: 'Cormorant Garamond', serif;
    color: var(--brass);
    font-style: italic;
  }
  .advisor-scroll {
    background: var(--paper);
    border: 1px solid var(--brass-soft);
    border-radius: 6px;
    height: 60vh;
    padding: 16px;
  }
  .msg-user {
    background: var(--ink);
    color: var(--paper);
    border-radius: 14px 14px 2px 14px;
    padding: 10px 14px;
    max-width: 80%;
    margin-left: auto;
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 0.95rem;
    line-height: 1.4;
    box-shadow: 0 1px 3px rgba(2,31,77,0.15);
  }
  .msg-ai {
    background: var(--paper-2);
    color: var(--ink-deep);
    border: 1px solid var(--brass-soft);
    border-radius: 14px 14px 14px 2px;
    padding: 12px 16px;
    max-width: 90%;
    font-family: 'Cormorant Garamond', serif;
    font-size: 1.1rem;
    line-height: 1.55;
  }
  .advisor-card {
    border: 1px solid var(--brass-soft);
    background: var(--paper);
    border-radius: 6px;
    transition: transform 0.2s, box-shadow 0.2s;
    cursor: pointer;
    width: 180px;
    overflow: hidden;
  }
  .advisor-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  }
  .advisor-card-img {
    width: 100%;
    height: 130px;
    object-fit: cover;
    display: block;
  }
  .advisor-card-body {
    padding: 8px 10px;
  }
  .advisor-card-name {
    font-family: 'Cormorant Garamond', serif;
    font-size: 0.95rem;
    color: var(--ink-deep);
    font-weight: 600;
    line-height: 1.2;
    margin-bottom: 2px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .advisor-card-price {
    font-family: 'Cormorant Garamond', serif;
    font-size: 0.95rem;
    color: var(--brass);
    font-weight: 600;
  }
  .advisor-input-row {
    background: var(--paper);
    border: 1px solid var(--brass-soft);
    border-radius: 999px;
    padding: 4px 8px 4px 16px;
  }
  .advisor-back {
    color: var(--brass) !important;
    font-family: 'Cormorant Garamond', serif;
  }
</style>
"""


class StyleAdvisor:
    def __init__(self, gemini_api_key: str, db_pool):
        self.api_key = (gemini_api_key or '').strip()
        self.pool = db_pool
        if self.api_key:
            genai.configure(api_key=self.api_key)
        self.has_gemini = bool(self.api_key)

    def _pool(self):
        return self.pool or getattr(app.state, 'pool', None)

    async def get_inventory_json(self) -> str:
        pool = self._pool()
        if not pool:
            return "[]"
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, nombre, tipo, precio, descripcion, tienda
                FROM muebles
                WHERE vendido = FALSE
                ORDER BY id DESC
                LIMIT 100
            """)
        return json.dumps([dict(r) for r in rows], default=str, ensure_ascii=False)

    async def chat(self, user_message: str, history: List[Dict]) -> str:
        if not self.has_gemini:
            return "El asesor no está disponible en este momento."
        inventory = await self.get_inventory_json()
        system_instruction = (
            "Eres un asesor experto en antigüedades de la tienda 'El Jueves' en Madrid.\n"
            "Tu función es ayudar a los clientes a encontrar muebles de nuestro inventario.\n"
            "REGLAS:\n"
            f"1. Solo puedes recomendar muebles que aparezcan en este inventario: {inventory}\n"
            "2. Cuando recomiendes un mueble, SIEMPRE incluye su ID con el formato exacto [ID:123]\n"
            "3. Responde en español, tono amable y experto en antigüedades\n"
            "4. Si no hay nada que se ajuste, dilo honestamente\n"
            "5. Máximo 3 recomendaciones por respuesta"
        )
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            system_instruction=system_instruction,
        )
        formatted_history = []
        for m in history:
            role = "user" if m.get("role") == "user" else "model"
            formatted_history.append({"role": role, "parts": [m.get("content", "")]})
        chat = model.start_chat(history=formatted_history)
        resp = await asyncio.to_thread(chat.send_message, user_message)
        return (getattr(resp, 'text', '') or '').strip()

    async def fetch_muebles(self, ids: List[int]) -> List[Dict]:
        pool = self._pool()
        if not pool or not ids:
            return []
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, nombre, precio FROM muebles WHERE id = ANY($1::int[]) AND vendido = FALSE",
                ids,
            )
        return [dict(r) for r in rows]


def advisor_chat_ui(advisor: StyleAdvisor):
    ui.add_head_html(ADVISOR_CSS)
    history: List[Dict] = []

    with ui.element('div').classes('advisor-shell'):
        with ui.column().classes('w-full items-center mb-3 gap-1'):
            ui.label('Asesor de Estilo').classes('advisor-title text-3xl')
            ui.label('Cuéntenos qué busca y le sugerimos piezas del catálogo').classes('advisor-sub text-sm')

        ui.button('← Volver al catálogo', on_click=lambda: ui.navigate.to('/')) \
            .props('flat dense').classes('advisor-back mb-3')

        scroll = ui.scroll_area().classes('advisor-scroll w-full')
        with scroll:
            messages = ui.column().classes('w-full gap-3')

        loading = ui.spinner(size='lg').classes('mx-auto my-2')
        loading.set_visibility(False)

        with ui.row().classes('advisor-input-row w-full items-center gap-2 mt-3'):
            user_input = ui.input(placeholder='Busco una cómoda art déco para un pasillo estrecho...') \
                .props('borderless dense').classes('flex-1')
            send_btn = ui.button(icon='send').props('round flat')

    async def render_message(role: str, text: str):
        with messages:
            if role == 'user':
                with ui.row().classes('w-full'):
                    ui.html(f'<div class="msg-user">{html.escape(text)}</div>')
            else:
                with ui.column().classes('w-full gap-2 items-start'):
                    clean = re.sub(r'\[ID:\s*(\d+)\]', r'#\1', text)
                    body = html.escape(clean).replace('\n', '<br>')
                    ui.html(f'<div class="msg-ai">{body}</div>')
                    ids = [int(x) for x in re.findall(r'\[ID:\s*(\d+)\]', text)]
                    if ids:
                        muebles = await advisor.fetch_muebles(ids)
                        if muebles:
                            with ui.row().classes('gap-3 mt-1 overflow-x-auto pb-2'):
                                for m in muebles:
                                    mid = m['id']
                                    card = ui.element('div').classes('advisor-card')
                                    card.on('click', lambda _e, _id=mid: ui.navigate.to(f'/?id={_id}'))
                                    with card:
                                        ui.html(f'<img class="advisor-card-img" src="/img/{mid}?thumb=1" alt="">')
                                        with ui.element('div').classes('advisor-card-body'):
                                            ui.html(f'<div class="advisor-card-name">{html.escape(str(m["nombre"]))}</div>')
                                            ui.html(f'<div class="advisor-card-price">{html.escape(str(m["precio"]))} €</div>')
        scroll.scroll_to(percent=1.0)

    async def send():
        text = (user_input.value or '').strip()
        if not text:
            return
        user_input.value = ''
        send_btn.disable()
        user_input.disable()
        loading.set_visibility(True)
        try:
            await render_message('user', text)
            ctx = history[-6:]
            reply = await advisor.chat(text, ctx)
            history.append({"role": "user", "content": text})
            history.append({"role": "assistant", "content": reply})
            await render_message('assistant', reply)
        except Exception as e:
            ui.notify(f'Error: {e}', type='negative')
        finally:
            loading.set_visibility(False)
            send_btn.enable()
            user_input.enable()

    send_btn.on('click', send)
    user_input.on('keydown.enter', send)
