import requests
import httpx
import json
from urllib.parse import urlencode
import asyncio
from api.schema import ScrapeData
import datetime
from bs4 import BeautifulSoup
import datetime

class Scrapy:

    def __init__(self):
        self.url = "https://job-search-api.svc.dhigroupinc.com/v1/dice/jobs/search"
        self.params = {
            'q': 'Backend',
            'location': 'California',
            'page': '1',
            'pageSize': '50',
            'fields': 'jobId|summary|title|postedDate|modifiedDate|jobLocation.displayName|detailsPageUrl|salary|companyPageUrl|positionId|companyName',
            'culture': 'en',
        }
        self.headers = headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/112.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.5',
            'x-api-key': '1YAt0R9wBg4WfsF9VB2778F5CHLAPMVW3WAZcKd8',
            'Origin': 'https://www.dice.com',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-GPC': '1',
            'DNT': '1',
        }

    async def start_scrape(self, **kwargs):
        async with httpx.AsyncClient() as client:
            print("--------Scrape Started-------")
            d1 = datetime.datetime.now()
            initial_job_data = await self.scrape_search(client=client, **kwargs)
            if initial_job_data:
                await self.db_handler(data=initial_job_data)
                print("----Initial data inserted-----")
                await self.scrape_job(client=client, jobs=initial_job_data)
                print("----skills and JD scrapped-----")
            print("--------Scrape Ended---------")
            d2 = datetime.datetime.now()
            total_time = d2-d1
            print("Time Taken: %s" % str(total_time))
            await client.aclose()

    async def scrape_search(self, **kwargs):
        params = {**self.params, **kwargs.get("params", {})}
        headers = {**self.headers, **kwargs.get("headers", {})}
        client = kwargs.get("client")
        response = None
        try:
            response = await client.get(
                url=kwargs.get("url", self.url),
                params=params,
                headers=headers
            )
            response.raise_for_status()
            response = response.json()["data"]
        except httpx.HTTPError as exc:
            print(f"HTTP Exception for {exc.request.url} - {exc}")
        return response

    async def scrape_job(self, **kwargs):
        client = kwargs.get("client")
        for job in kwargs.get("jobs"):
            update_data = {}
            try:
                job_page = await client.get(url=job["detailsPageUrl"])
                soup = BeautifulSoup(job_page.content, "html.parser")
                find_skills = soup.find("div", {"data-cy": "skillsList"})
                if find_skills:
                    skills = [skill.text.strip() for skill in find_skills.findChildren() ]
                    update_data["skills"] = ",".join(skills[:-1])
                find_jd = soup.find("div", {"data-testid": "jobDescriptionHtml"})
                if find_jd:
                    update_data["description"] = find_jd.text
            except httpx.HTTPError as exc:
                print(f"HTTP Exception for {exc.request.url} - {exc}")
            
            if "skills" in update_data.keys() or "description" in update_data.keys():
                await ScrapeData.update({**update_data}).where(
                    ScrapeData.jobId == job["jobId"]
                )
                print("-----------Updated %s-------------" % job["jobId"])
        return True
            


    async def db_handler(self, **kwargs):
        await ScrapeData.create_table(if_not_exists=True) 
        for data in kwargs.get("data"):
            data['postedDate'] = datetime.datetime.strptime(
                data['postedDate'],
                '%Y-%m-%dT%H:%M:%S%z'
            )
            data['modifiedDate'] = datetime.datetime.strptime(
                data['modifiedDate'],
                '%Y-%m-%dT%H:%M:%S%z'
            )
            data["jobLocation"] = data["jobLocation"]["displayName"]
            await ScrapeData.insert(ScrapeData(**data))

# if __name__ == "__main__":
#     scrape = Scrapy()
#     asyncio.run(scrape.start_scrape())
