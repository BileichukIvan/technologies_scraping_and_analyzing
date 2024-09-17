import json
import os
import re
from typing import Generator, Iterable

import scrapy
from pydispatch import dispatcher
from scrapy import signals, Request
from scrapy_selenium import SeleniumRequest
from selenium import webdriver

from scrapy.http import Response
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.common.exceptions import (
    TimeoutException,
    ElementNotInteractableException
)
from selenium.webdriver.chrome.options import Options


class VacancyItem(scrapy.Item):
    title = scrapy.Field()
    company = scrapy.Field()
    salary = scrapy.Field()
    location = scrapy.Field()
    description = scrapy.Field()
    technologies = scrapy.Field()


class TechnologiesSpiderSpider(scrapy.Spider):
    name = "technologies_spider"
    allowed_domains = ["jobs.dou.ua"]
    start_urls = ["https://jobs.dou.ua/vacancies/?category=Python"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        self.driver = webdriver.Chrome(options=chrome_options)
        dispatcher.connect(self.spider_closed, signal=signals.spider_closed)
        config_path = os.path.join(
            os.path.dirname(__file__),
            "../technology_tags.json"
        )
        with open(config_path, "r") as f:
            config = json.load(f)
            self.technologies = config.get("technologies", [])

    def start_requests(self) -> Iterable[Request]:
        url = "https://jobs.dou.ua/vacancies/?category=Python"
        yield SeleniumRequest(url=url, callback=self.parse)

    def parse(
            self,
            response: Response,
            **kwargs
    ) -> Generator[scrapy.Request, None, None]:
        self.driver.get(response.url)
        while True:
            try:
                more_button = WebDriverWait(self.driver, 10).until(
                    expected_conditions.element_to_be_clickable(
                        (By.CSS_SELECTOR, ".more-btn a")
                    )
                )
                more_button.click()
            except (TimeoutException, ElementNotInteractableException):
                print("Кнопка 'Більше вакансій' неактивна, завершення.")
                break

        html = self.driver.page_source
        sel = scrapy.Selector(text=html)

        for vacancy in sel.css(".l-vacancy"):
            url = vacancy.css("a::attr(href)").get()
            salary = vacancy.css("span.salary::text").get()
            location = vacancy.css("span.cities::text").get()

            if url is not None:
                vacancy_url = url
                yield scrapy.Request(
                    vacancy_url,
                    callback=self.parse_vacancy,
                    meta={
                        "salary": salary,
                        "location": location,
                    }
                )

    def parse_vacancy(self, response: Response) -> dict:
        page_content = response.css(
            "div.b-typo.vacancy-section *::text"
        ).getall()
        description = " ".join(
            [text.strip() for text in page_content if text.strip()]
        )
        description = description.replace(u"\xa0", u" ")
        technologies_in_description = self.extract_technologies(
                    description, self.technologies
                )
        vacancy_exp = VacancyItem(
            title=response.css(".g-h2::text").get(),
            company=response.css(".l-n > a::text").get(),
            salary=response.meta["salary"],
            location=response.meta["location"],
            description=description,
            technologies=technologies_in_description,
        )
        yield vacancy_exp

    @staticmethod
    def extract_technologies(description, tech_list):
        if description:
            found_technologies = [
                tech
                for tech in tech_list
                if re.search(
                    r"\b" + re.escape(tech) +
                    r"\b", description, re.IGNORECASE
                )
            ]
            return ", ".join(found_technologies)
        return "NaN"

    def spider_closed(self, spider):
        spider.logger.info("Spider closed: %s", spider.name)
        self.driver.quit()
