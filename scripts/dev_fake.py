"""DEV ONLY: run the server with a scripted fake model (no API keys) to test the UI end to end."""
import asyncio, sys
sys.path.insert(0, ".")
import uvicorn
from app import agent, config, main  # noqa
config.ANTHROPIC_API_KEY = config.ANTHROPIC_API_KEY or "fake"; config.OPENAI_API_KEY = config.OPENAI_API_KEY or "fake"
SQL = """SELECT year, count(*) AS deals, count(*) FILTER (WHERE is_cancelled) AS cancelled,
 round(sum(volume_norm) FILTER (WHERE NOT is_cancelled),1) AS tonnes,
 list(deal_id ORDER BY amount_uzs DESC)[1:5] AS sample_deal_ids
 FROM deals WHERE product_base='топливо дизельное' GROUP BY year ORDER BY year"""
async def fake(run, emit, deadline):
    await asyncio.sleep(0.6); await run.exec_tool('find_product', {'query': 'dizel'}, emit)
    await asyncio.sleep(0.8); r = await run.exec_tool('run_sql', {'purpose': 'Dizel yoqilg‘isi yillar bo‘yicha', 'sql': SQL}, emit)
    row = [x for x in r['rows'] if x[0] == 2025][0]
    tt = f"{row[3]:,.1f}".replace(',', ' ').replace('.', ',')
    await asyncio.sleep(0.8)
    await run.exec_tool('final_answer', {'status': 'answered', 'language': 'uz',
        'answer': f"2025-yilda **{tt}** tonna dizel yoqilg‘isi sotilgan (bekor qilinganlarsiz).\n- Jami {row[1]} ta bitim tuzilgan, shundan {row[2]} tasi bekor qilingan.\n- Barcha 3 marka kiritilgan: ДТ-Е-К5, ДТ-З-К5, ДТ-Л-К5.",
        'speech': "2025-yilda taxminan yuz yetmish olti ming tonna dizel sotilgan.",
        'key_figures': [{'label': 'Sotilgan hajm, tonna', 'value': row[3], 'unit': 't', 'query_id': run.tag + '1'}],
        'assumptions': ['Bekor qilingan bitimlar hajmga kiritilmadi', 'Kilogramm tonnaga o‘girildi', 'Barcha dizel markalari (product_base = топливо дизельное)'],
        'followups': ['Dizel narxi 2025-yilda qanday o‘zgargan?', 'Eng ko‘p dizel sotgan kompaniya qaysi?', 'Bu 2024-yil bilan solishtirganda qancha?'], 'used_query_ids': [run.tag + '1'], 'evidence_query_id': run.tag + '1',
        'chart': {'query_id': run.tag + '1', 'type': 'bar', 'x': 'year', 'y': 'tonnes', 'title': 'Dizel, tonna'}}, emit)
    return run
agent.claude_loop = fake; agent.gpt_loop = fake
uvicorn.run(main.app, host="0.0.0.0", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
