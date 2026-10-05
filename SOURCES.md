# Sources

Checked on 2026-10-05 from this PC. A feed URL is stored only when the address returned an RSS document. Trust scores are starting publisher defaults, not a claim that every article is true.

The same records are inserted with:

```powershell
cd "C:\Users\Kaby\mycursorcode\GhanaEd News\backend"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.db.seed
```

Running the seed again does not duplicate or overwrite a source you have edited.

## Feeds the collector reads

| Source | Type | How it is found | Address | Check interval | Parser | Review |
| --- | --- | --- | --- | --- | --- | --- |
| MyJoyOnline Education | News | RSS | https://www.myjoyonline.com/feed/ | 3 hours | generic_rss | Yes |
| Adom Online Education | News | RSS | https://www.adomonline.com/category/education/feed/ | 3 hours | generic_rss | Yes |
| 3News | News | RSS | https://3news.com/feed/ | 3 hours | generic_rss | Yes |
| Ghana Tertiary Education Commission | Government | RSS | https://gtec.edu.gh/feed/ | 12 hours | generic_rss | Yes |

3News does not publish an education-only feed. `https://3news.com/category/education/feed/` returned 404, so the general feed is stored and the relevance rules drop stories that are not about education.

MyJoyOnline's education category address redirected to an empty comments feed on 2026-10-05. The collector uses the site's general RSS feed instead, and the same relevance rules apply.

The collector skips the three sources below because they have no feed URL.

## Registered, not fetched yet

| Source | Type | How it is found | What was checked | Check interval |
| --- | --- | --- | --- | --- |
| Graphic Online Education | News | HTML page | https://www.graphic.com.gh/news/education.html returned HTML. `/feed` returned 404. | 24 hours |
| Ministry of Education | Government | HTML page | https://moe.gov.gh/ returned HTML. `/feed` returned 404. | 24 hours |
| Ghana Education Service | Government | HTML page | Articles live at https://ges.gov.gh/articles.php. A direct request from this PC timed out, so no feed URL is stored. | 24 hours |

These three have no fallback fetcher yet. Phase 3 should skip a source when `feed_url` is empty.

## Checked and left out

- Citi Newsroom publishes an RSS service page, but `https://citinewsroom.com/rss-service/general.rss` returned 404 and `https://www.citinewsroom.com/?feed=rss2` returned the homepage.
- Ghana News Agency `https://gna.org.gh/feed/` returned HTML.
- GhanaWeb `https://www.ghanaweb.com/GhanaHomePage/rss/news.xml` returned a challenge page.
- WAEC Ghana `https://www.waecgh.org/` timed out.

Add any of these later through `POST /sources` once a public feed or page is confirmed. That does not require an application code change.
