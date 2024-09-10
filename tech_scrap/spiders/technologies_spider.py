import scrapy


class TechnologiesSpiderSpider(scrapy.Spider):
    name = "technologies_spider"
    allowed_domains = ["jobs.dou.ua"]
    start_urls = ["https://jobs.dou.ua/vacancies/?category=Python"]

    def parse(self, response):
        pass
