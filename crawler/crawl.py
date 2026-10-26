import multiprocessing
from bs4 import BeautifulSoup
from collections import defaultdict
from copy import copy
from queue import PriorityQueue, Empty
from concurrent.futures import ThreadPoolExecutor, wait, as_completed
from url_normalize import url_normalize
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import re
import time
import requests
import pickle
import os

os.makedirs("data/crawl", exist_ok=True)

class Frontier(object):
    def __init__(self):
        self.queue = PriorityQueue()
        self.set = set()

    def head(self):
        string = "["
        for i in range(10):
            try:
                string += "{}, ".format(self.queue.queue[i][1][0])
            except:
                pass
        return string + "]"

    def size(self):
        return self.queue.qsize()

    def add(self, score, url, wave):
        self.set.add(url)
        self.queue.put((score, [url, wave, score]))

    def addIfNew(self, score, url, wave):
        if url not in self.set:
            self.add(score, url, wave)

    def pop(self, timeout=None):
        item = self.queue.get(timeout=timeout)
        self.set.remove(item[1][0])
        return item[0], item[1][0], item[1][1]

    def rebalance(self):
        newQueue = PriorityQueue()
        for item in self.queue.queue:
            score = len(inlinkList[item[1][0]]) * (-10) # inlink_score = -10
            newQueue.put((item[1][2] + score, [item[1][0], item[1][1], item[1][2]]))
        self.queue = newQueue


visited = set([])
frontier = Frontier()
robots = {}
running = {}
keywords = ["social", "justice", "racism", "bipoc", "diversity", "equity", "gender", "bias", "inclusion", "race", "ally", "culture", "bigotry", "health", "care", "intersectionality", "oppression", "racial", "disparity", "accountability", "discrimination", "equality", "harassment", "human", "rights", "right", "privilege", "black", "lives", "matter", "color blind", "patriarchy", "civil", "disability", "special", "affirmative", "action", "needs", "ableism", "accessibility", "adaptive", "technology", "differently", "abled", "handicap", "hearing", "loss", "visually", "impaired", "physical", "mental"]
tld = [".gov", ".edu", ".org"]
# domains = ["en.wikipedia.org"]
documentCount = 0
documentFileNum = 0
documentIncrement = 0
rebal_power = 0
inlinkList = defaultdict(set)
outlinkList = defaultdict(set)
jobs = set()
document = ""
collect = 10000
max_workers = 100
executor = ThreadPoolExecutor(max_workers=max_workers)


def process_url(url, base_url=None):
    # makes relative URLs absolute
    if base_url:
        url = urljoin(base_url, url)
    # `normalize_url` does the following:
    # - converts scheme and host to lower case
    # - removes port 80 from http URLs and port 443 from HTTPS URLs
    # - removes duplicate slashes
    try:
        url = url_normalize(url)
    except:
        print("URL normalizing failed: {}".format(url))
        pass
    # remove the fragment from the URL
    url = url.split('#')[0]
    return url


def score_link(url, curr_score, anchor_text, wave):
    score = wave * 10000
    for word in keywords:
        if word in url or word in anchor_text:
            score -= 100
    # if urlparse(url).netloc in domains:
    #     score -= 20
    score += curr_score / 100
    return score


def parse_links(html, current_score, current_url, current_wave):
    soup = BeautifulSoup(html, 'html.parser')
    Anchor_Tags = soup.find_all('a', href=True)
    for link in Anchor_Tags:
        url = link['href']
        if link.get("hreflang", "en") == "en" and link.get("lang", "en") == "en" and "action=" not in url and "wikipedia.org/w/index.php" not in url and "tel:" not in url:
            canon_url = process_url(url, base_url=current_url)
            if canon_url not in visited:
                score = score_link(canon_url, current_score, link.text.strip(), current_wave + 1)
                frontier.addIfNew(score, canon_url, current_wave + 1)
                inlinkList[canon_url].add(current_url)
                outlinkList[current_url].add(canon_url)
            else:
                inlinkList[canon_url].add(current_url)


def saveData(html, current_url):
    global document
    global documentCount

    docno = current_url
    title = ""
    content = ""
    soup = BeautifulSoup(html, "html.parser")

    if soup.find('title') is not None:
        title = soup.find('title').text.strip()

    for p in soup.find_all(["p"]):
        content += re.sub('[^A-Za-z0-9]+', ' ', p.get_text()) + " "
    content = " ".join(content.split())

    if len(content) > 100:
        text = ("<DOC>\n<DOCNO>" + docno + "</DOCNO>\n<HEAD>" + title + "</HEAD>\n<TEXT>" + content + "</TEXT>\n</DOC>\n")

        global documentFileNum
        global documentCount
        global documentIncrement

        if documentIncrement == 50:
            documentFileNum += 1
            documentIncrement = 1
        else:
            documentIncrement += 1

        f = open("data/crawl/document{}.txt".format(documentFileNum), "a", encoding="utf-8")
        f.write(text)
        f.close()
        documentCount += 1
        print(">{} - Saved {}".format(documentCount, docno))
    return


def post_scrape_callback(res):
    try:
        if res.result():
            result, current_score, current_url, current_wave = res.result()
            if result.status_code == 200:
                parse_links(result.text, current_score, current_url, current_wave)
                saveData(result.text, current_url)
        jobs.remove(res)
    except:
        jobs.remove(res)
        pass


def scrape_page(url, current_score, current_wave):
    try:
        if not (robot_check(url) and valid_link(url)):
            return

        domain = urlparse(url).netloc

        # Polite policy to wait one second per domain
        if domain in running:
            while time.time() - running[domain] <= 1:
                pass
        running[domain] = time.time()

        print("Scraping URL: {}".format(url))
        res = requests.get(url, timeout=(3, 30))

        return res, current_score, url, current_wave
    except requests.RequestException:
        return


def robot_check(url):
    parsed = urlparse(url)
    robot = parsed.scheme + "://" + parsed.netloc + "/robots.txt"
    if robot in robots:
        fetched = robots[robot]
        return fetched.can_fetch("*", url)
    else:
        try:
            rp = RobotFileParser()
            rp.set_url(robot)
            rp.read()
            robots.update({robot: rp})
            return rp.can_fetch("*", url)
        except:
            return False


def valid_link(url):
    try:
        r = requests.head(url)
        if 'content-type' in r.headers:
            if "text/html" in r.headers['content-type']:
                if 'content-langauge' in r.headers and 'en' != r.headers['content-language']:
                    print(url + " lang invalid.")
                    return False
                return True
            else:
                print(url + " content-type invalid: " + r.headers['content-type'])
                return False
        else:
            return True
    except:
        return False


def saveLinks():
    print("--------- Saving links ---------")
    with open('data/crawl/inlink.pickle', 'wb') as handle:
        pickle.dump(inlinkList, handle, protocol=pickle.HIGHEST_PROTOCOL)
    with open('data/crawl/outlink.pickle', 'wb') as handle:
        pickle.dump(outlinkList, handle, protocol=pickle.HIGHEST_PROTOCOL)
    # f = open("data/crawl/inlinks", "w", encoding="utf-8")
    # inlinkContent = ""
    # for il in inlinkList:
    #     inlinkContent += il + "<:>"
    #     for l in inlinkList[il]:
    #         inlinkContent += l + "<,>"
    #     inlinkContent += "\n"
    # f.write(inlinkContent)
    # f.close()
    # print("Inlinks Done!")
    #
    # f = open("data/crawl/outlinks", "w", encoding="utf-8")
    # outlinkContent = ""
    # for ol in outlinkList:
    #     outlinkContent += ol + "<:>"
    #     for l in outlinkList[ol]:
    #         outlinkContent += l + "<,>"
    #     outlinkContent += "\n"
    # f.write(outlinkContent)
    # f.close()
    # print("Outlinks Done!")
    print("--------- Finished saving links ---------")


def crawler():
    global rebal_power
    while True:
        if documentCount > collect:
            print("Cancelling jobs")
            executor.shutdown(wait=True, cancel_futures=True)
            saveLinks()
            break
        else:
            try:
                if len(visited) == rebal_power * 100 or len(visited) == pow(2, rebal_power):
                    rebal_power += 1
                    print("--------- Rebalance ---------")
                    # print("Before: " + frontier.head())
                    frontier.rebalance()
                    # print("After: " + frontier.head())
                    print("--------- Finished Rebalance ---------")

                    print("Waiting")
                    # print("Before: {}".format(len(jobs)))
                    while len(jobs) > 0:
                        time.sleep(1)
                        print("Jobs left: {}".format(len(jobs)))
                        pass
                    # print("After: {}".format(len(jobs)))

                    saveLinks()
                    # if len(visited) == rebal_power * 1000:
                    #     saveLinks()
                    print("Resuming")
                else:
                    current_score, current_url, current_wave = frontier.pop(timeout=60)
                    if current_url not in visited:
                        visited.add(current_url)
                        job = executor.submit(scrape_page, current_url, current_score, current_wave)
                        jobs.add(job)
                        job.add_done_callback(post_scrape_callback)
            except Empty:
                print("Empty")
                return
            except Exception as e:
                print(e)
                continue
    print("Finished crawling")

seed = ["https://en.wikipedia.org/wiki/Social_justice",
        "https://en.wikipedia.org/wiki/Disability_rights_movement",
        "https://www.aclu.org/issues/disability-rights","https://www.ncil.org/",
        "https://www.ada.gov/"]

for url in seed:
    frontier.add(0, url, 0)

crawler()