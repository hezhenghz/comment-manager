import os
from datetime import datetime
from openpyxl import Workbook
from app.models import Comment
from app.models import ReportTask

EXPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "exports")
os.makedirs(EXPORT_DIR, exist_ok=True)


def export_excel(task: ReportTask, comments: list[Comment]) -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = "Comments"
    ws.append(["Platform", "Source", "Author", "Content", "Sentiment", "Category", "Language", "Published", "URL"])

    for c in comments:
        ws.append([
            c.platform, c.source_type, c.author_name, c.content,
            c.sentiment, c.category, c.content_lang,
            c.published_at.isoformat() if c.published_at else "",
            c.source_url or "",
        ])

    filename = f"report-{task.id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.xlsx"
    file_path = os.path.join(EXPORT_DIR, filename)
    wb.save(file_path)
    return file_path


def export_pdf(task: ReportTask, comments: list[Comment]) -> str:
    from weasyprint import HTML

    html = "<html><head><meta charset='utf-8'><style>body{font-family:sans-serif;padding:20px;}table{border-collapse:collapse;width:100%;}th,td{border:1px solid #555;padding:6px;font-size:12px;}</style></head><body>"
    html += "<h2>Comment Report</h2><table><tr><th>Platform</th><th>Source</th><th>Author</th><th>Content</th><th>Sentiment</th><th>Category</th></tr>"
    for c in comments:
        html += f"<tr><td>{c.platform}</td><td>{c.source_type}</td><td>{c.author_name or ''}</td><td>{c.content[:200]}</td><td>{c.sentiment or ''}</td><td>{c.category or ''}</td></tr>"
    html += "</table></body></html>"

    filename = f"report-{task.id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pdf"
    file_path = os.path.join(EXPORT_DIR, filename)
    HTML(string=html).write_pdf(file_path)
    return file_path
