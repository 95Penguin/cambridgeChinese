import scrapy
from urllib.parse import urljoin
import json
import logging
import os  # 导入 os 模块用于文件操作

class DictionarySpider(scrapy.Spider):
    name = 'dictionary'
    start_urls = ['https://dictionary.cambridge.org/browse/english-chinese-simplified/']

    custom_settings = {
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Referer': 'https://dictionary.cambridge.org/',
            'Origin': 'https://dictionary.cambridge.org'
        },
        'COOKIES_ENABLED': True,
        'DOWNLOAD_DELAY': 3,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'CONCURRENT_REQUESTS': 1
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.first_level_urls = []
        self.second_level_urls = []
        self.word_urls = []
        self.current_first_level_url = None  # 当前处理的一级目录链接
        self.current_first_level_data = []  # 当前一级目录的数据

        # 初始化日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            filename='dictionary_spider.log'
        )
        self.logger.info("Spider initialized")

        # 确保 data 文件夹存在
        if not os.path.exists('data'):
            os.makedirs('data')

    def clean_text(self, text):
        if not text:
            return ''
        return text.strip().rstrip('，；').strip()

    def start_requests(self):
        yield scrapy.Request(
            url=self.start_urls[0],
            callback=self.parse_first_level,
            meta={
                'dont_merge_cookies': True,
                'handle_httpstatus_list': [403, 404, 500, 503]
            },
            dont_filter=True
        )

    def parse_first_level(self, response):
        # 获取一级目录链接
        links = response.xpath('//div[@class="hfl-s lt2b lmt-10 lmb-25 lp-s_r-20"]//ul[@class="hul-i hul-ib lm-0"]/li/a/@href').getall()
        self.first_level_urls = [urljoin(response.url, link) for link in links]

        self.logger.info(f"Found {len(self.first_level_urls)} first-level URLs")

        # 开始处理第一个一级目录
        if self.first_level_urls:
            first_level_url = self.first_level_urls.pop(0)
            self.current_first_level_url = first_level_url  # 设置当前一级目录链接
            yield scrapy.Request(
                url=first_level_url,
                callback=self.parse_second_level,
                dont_filter=True
            )

    def parse_second_level(self, response):
        # 获取二级目录链接
        self.second_level_urls = response.xpath('//div[@class="hdf ff-50 lmt-15 i-browse"]//a[@class="hlh32 hdb dil tcbd"]/@href').getall()
        
        self.logger.info(f"Found {len(self.second_level_urls)} second-level URLs")

        # 开始处理第一个二级目录
        if self.second_level_urls:
            first_second_level_url = urljoin(response.url, self.second_level_urls.pop(0))
            yield scrapy.Request(
                url=first_second_level_url, 
                callback=self.parse_word_links,
                dont_filter=True
            )
        # 如果当前一级目录的二级目录已处理完，保存当前一级目录的数据并处理下一个一级目录
        elif self.first_level_urls:
            # 保存当前一级目录的数据
            self.save_first_level_data()
            # 处理下一个一级目录
            next_first_level_url = self.first_level_urls.pop(0)
            self.current_first_level_url = next_first_level_url
            yield scrapy.Request(
                url=next_first_level_url, 
                callback=self.parse_second_level,
                dont_filter=True
            )

    def parse_word_links(self, response):
        # 获取当前页面的单词链接
        current_word_links = response.xpath('//div[contains(@class, "hlh32 han")]/a[@class="tc-bd"]/@href').getall()
        
        # 将单词链接添加到总列表
        self.word_urls.extend([urljoin(response.url, link) for link in current_word_links])

        # 如果当前页面有单词链接，开始爬取第一个单词的详细内容
        if self.word_urls:
            first_word_url = self.word_urls.pop(0)
            yield scrapy.Request(
                url=first_word_url, 
                callback=self.parse_word_details,
                dont_filter=True
            )
        # 如果当前二级目录的单词链接已处理完，处理下一个二级目录
        elif self.second_level_urls:
            next_second_level_url = urljoin(response.url, self.second_level_urls.pop(0))
            yield scrapy.Request(
                url=next_second_level_url, 
                callback=self.parse_word_links,
                dont_filter=True
            )
        # 如果当前一级目录的二级目录已处理完，保存当前一级目录的数据并处理下一个一级目录
        elif self.first_level_urls:
            # 保存当前一级目录的数据
            self.save_first_level_data()
            # 处理下一个一级目录
            next_first_level_url = self.first_level_urls.pop(0)
            self.current_first_level_url = next_first_level_url
            yield scrapy.Request(
                url=next_first_level_url, 
                callback=self.parse_second_level,
                dont_filter=True
            )

    def parse_word_details(self, response):
        # word = response.xpath('//div[contains(@class, "di-title")]//span[contains(@class, "hw")]/text()').get('').strip()
        word = response.xpath('//div[contains(@class, "di-title")]//span[contains(@class, "hw")]/text() | //div[contains(@class, "di-title")]//b/text()').get('').strip()
        word_data = []

        self.logger.info(f"Parsing word details for: {word}")

        # 获取所有词性块
        # pos_blocks = response.xpath('//div[contains(@class, "entry-body")]//div[contains(@class, "pr entry-body__el")]')

        # 检测是否为习语（idiom）或短语（phrase）
        is_idiom = bool(response.xpath('//div[contains(@class, "idiom-block")]'))
        is_phrase = bool(response.xpath('//span[contains(@class, "phrase-di-block dphrase-di-block")]'))
        is_phrase_verb = bool(response.xpath('//div[contains(@class, "pv-block")]'))

        if is_idiom:
            # 处理习语（idiom）
            pos_blocks = response.xpath('//div[contains(@class, "pr idiom-block")]')
        elif is_phrase:
            # 处理短语（phrase）
            pos_blocks = response.xpath('//span[contains(@class, "phrase-di-block dphrase-di-block")]')
        elif is_phrase_verb:
            # 处理动词短语（phrasal verb）
            pos_blocks = response.xpath('//div[contains(@class, "pv-block")]')
        else:
            # 处理普通单词
            pos_blocks = response.xpath('//div[contains(@class, "entry-body")]//div[contains(@class, "pr entry-body__el")]')

        for pos_block in pos_blocks:
            entry = {
                "word": word,
                "part_of_speech": self.clean_text(pos_block.xpath('.//div[contains(@class, "posgram")]//span[contains(@class, "pos")]/text()').get(''))
            }

            # 获取发音
            uk_pron = ''.join(pos_block.xpath('.//span[contains(@class, "uk dpron-i")]//span[contains(@class, "ipa")]/text()').getall()).strip()
            uk_mp3 = pos_block.xpath('.//span[contains(@class, "uk dpron-i")]//source[@type="audio/mpeg"]/@src').get('')
            if uk_pron:
                entry['uk_pronunciation'] = {
                    'pron': f"/{uk_pron}/",
                    'audio_url': urljoin(response.url, uk_mp3) if uk_mp3 else None
                }

            us_pron = ''.join(pos_block.xpath('.//span[contains(@class, "us dpron-i")]//span[contains(@class, "ipa")]/text()').getall()).strip()
            us_mp3 = pos_block.xpath('.//span[contains(@class, "us dpron-i")]//source[@type="audio/mpeg"]/@src').get('')
            if us_pron:
                entry['us_pronunciation'] = {
                    'pron': f"/{us_pron}/",
                    'audio_url': urljoin(response.url, us_mp3) if us_mp3 else None
                }

            # 获取词义
            senses = []
            for sense_block in pos_block.xpath('.//div[contains(@class, "def-block")]'):
                sense = {}

                # 获取指导词（guide_word）
                guide_word_xpath = './/ancestor::div[contains(@class, "pr dsense")]/h3[contains(@class, "dsense_h")]/span[contains(@class, "guideword dsense_gw")]/span/text()'
                guide_word = self.clean_text(sense_block.xpath(guide_word_xpath).get(''))
                if guide_word:
                    sense['guide_word'] = guide_word.strip('()').strip()

                # 获取定义
                def_parts = sense_block.xpath('.//div[contains(@class, "ddef_d")]//text()').getall()
                def_text = ' '.join([text.strip() for text in def_parts if text.strip()])
                if def_text:
                    definition = {
                        "definition": def_text,
                        "def_translation": self.clean_text(''.join(sense_block.xpath('.//div[@class="def-body ddef_b"]/span[contains(@class, "dtrans-se") and not(contains(@class, "hdb"))]//text()').getall()).strip()),
                        "level": self.clean_text(sense_block.xpath('.//span[contains(@class, "epp-xref")]/text()').get('')),
                        "attribute": self.clean_text(''.join(sense_block.xpath('.//div[contains(@class, "ddef_h")]//span[contains(@class, "gram dgram")]/a//text()').getall())),
                        "examples": []
                    }

                    # 获取例句
                    examples = []
                    for example in sense_block.xpath('.//div[contains(@class, "examp")]'):
                        ex = {
                            "text": self.clean_text(''.join(example.xpath('.//span[contains(@class, "eg")]//text()').getall())),
                            "translation": self.clean_text(example.xpath('.//span[contains(@class, "trans")]/text()').get(''))
                        }
                        if ex.get('text') or ex.get('translation'):
                            examples.append(ex)

                    definition['examples'] = examples

                    # 将定义添加到 sense 中
                    if 'definitions' not in sense:
                        sense['definitions'] = []
                    sense['definitions'].append(definition)

                # 获取更多例句（more_examples）
                more_examples = []
                more_examples_block = sense_block.xpath('.//following-sibling::div[contains(@class, "daccord")][1]//ul[contains(@class, "hul-u")]//li')
                for more_example in more_examples_block:
                    more_ex = {
                        "text": self.clean_text(''.join(more_example.xpath('.//text()').getall()))
                    }
                    if more_ex.get('text'):
                        more_examples.append(more_ex)

                # 如果存在 more_examples，将其关联到当前 sense 或 guide_word
                if more_examples:
                    if 'guide_word' in sense:
                        sense['more_examples'] = more_examples
                    else:
                        sense['more_examples'] = more_examples

                # 如果当前 sense 已经有 guide_word，则尝试合并定义
                if sense.get('guide_word'):
                    existing_sense = next((s for s in senses if s.get('guide_word') == sense['guide_word']), None)
                    if existing_sense:
                        existing_sense['definitions'].extend(sense['definitions'])
                        if 'more_examples' in sense:
                            existing_sense['more_examples'] = sense['more_examples']
                    else:
                        senses.append(sense)
                else:
                    senses.append(sense)

            if senses:
                entry['senses'] = senses

            # 获取短语动词和习语
            phrasal_verbs = []
            for phrasal_verb in response.xpath('//div[contains(@class, "xref phrasal_verbs")]//div[contains(@class, "lcs")]//a'):
                phrasal_verb_text = ' '.join(phrasal_verb.xpath('.//text()').getall())
                phrasal_verbs.append({
                    "phrasal_verb": self.clean_text(phrasal_verb_text),
                    "link": urljoin(response.url, phrasal_verb.xpath('.//@href').get(''))
                })

            idioms = []
            for idiom in response.xpath('//div[contains(@class, "xref idioms")]//div[contains(@class, "lcs")]//a'):
                idiom_text = ' '.join(idiom.xpath('.//text()').getall())
                idioms.append({
                    "idiom": self.clean_text(idiom_text),
                    "link": urljoin(response.url, idiom.xpath('.//@href').get(''))
                })

            if phrasal_verbs:
                entry['phrasal_verbs'] = phrasal_verbs

            if idioms:
                entry['idioms'] = idioms

            word_data.append(entry)


        yield {
            'url': response.url,
            'data': word_data
        }


        self.current_first_level_data.append({
            'url': response.url,
            'data': word_data
        })


        # 处理下一个单词
        if self.word_urls:
            next_word_url = self.word_urls.pop(0)
            yield scrapy.Request(
                url=next_word_url, 
                callback=self.parse_word_details,
                dont_filter=True
            )
        # 如果当前二级目录的单词已处理完，处理下一个二级目录
        elif self.second_level_urls:
            next_second_level_url = urljoin(response.url, self.second_level_urls.pop(0))
            yield scrapy.Request(
                url=next_second_level_url, 
                callback=self.parse_word_links,
                dont_filter=True
            )
        # 如果当前一级目录的二级目录已处理完，保存当前一级目录的数据并处理下一个一级目录
        elif self.first_level_urls:
            # 保存当前一级目录的数据
            self.save_first_level_data()
            # 处理下一个一级目录
            next_first_level_url = self.first_level_urls.pop(0)
            self.current_first_level_url = next_first_level_url
            yield scrapy.Request(
                url=next_first_level_url, 
                callback=self.parse_second_level,
                dont_filter=True
            )

    def save_first_level_data(self):
        """
        保存当前一级目录的数据到 JSON 文件
        """
        if self.current_first_level_url:
            # 获取一级目录链接的结尾作为文件名
            folder_name = self.current_first_level_url.split('/')[-2]  # 获取倒数第二部分作为文件名
            file_name = f"{folder_name}.json"
            file_path = os.path.join('data', file_name)  # 保存到 data 文件夹

            # 将当前一级目录的数据写入 JSON 文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.current_first_level_data, f, ensure_ascii=False, indent=2)

            self.logger.info(f"Saved data for {folder_name} to {file_path}")
            # 清空当前一级目录的数据
            self.current_first_level_data = []