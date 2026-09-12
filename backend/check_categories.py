from google_books import search_books

results = search_books('subject:"Fiction"', max_results=5)
for book in results:
    print(book["title"], "->", book["categories"])