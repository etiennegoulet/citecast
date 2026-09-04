# import httpx
# import feedparser

# params = {
#     "search_query": "cat:cs.AI OR cat:cs.LG OR cat:cs.CL OR cat:cs.MA",
#     "sortBy": "submittedDate",
#     "sortOrder": "descending",
#     "max_results": 10,
# }

# response = httpx.get("http://export.arxiv.org/api/query", params=params, follow_redirects=True)
# print(response.status_code)
# # print(response.text)
# feed = feedparser.parse(response.text)
# entry0 = feed.entries[0]
# print(entry0.keys())

from ai_intelligence.sources.arxiv import fetch_arxiv
from ai_intelligence.store import insert_items

items = fetch_arxiv(max_results=5)
inserted, skipped = insert_items(items)
print(f'{inserted} inserted, {skipped} skipped')