import asyncio, sys
sys.path.insert(0, r'c:\MediaMind')
from app.core.external_apis import ExternalAPIClient

async def main():
    async with ExternalAPIClient() as client:
        results = await client.search_steam('counter strike', 3)
        print('count', len(results))
        for item in results:
            print(item['title'])
            print(item['description'][:120])
            print(item['external_id'])
            print('---')

asyncio.run(main())
