import re
import os
from collections import defaultdict
from tqdm import tqdm
from elasticsearch7.helpers import streaming_bulk
from concurrent.futures import ThreadPoolExecutor, as_completed
import pickle
from es_client import get_client, INDEX_NAME, AUTHOR_NAME

es = get_client()

CRAWL_DIR = "data/crawl/"

crawled_info = []
with open(CRAWL_DIR + 'inlink.pickle', 'rb') as handle:
    inlinkList = pickle.load(handle)
with open(CRAWL_DIR + 'outlink.pickle', 'rb') as handle:
    outlinkList = pickle.load(handle)

# Go through all the crawled document files
for filename in os.listdir(CRAWL_DIR):
    if not (filename.startswith("document") and filename.endswith(".txt")):
        continue
    file_path = os.path.join(CRAWL_DIR, filename)
    file = open(file_path, 'r', encoding="utf8")
    lines = file.readlines()

    raw_doc = ""
    start = False
    url = ""
    for line in lines:
        if start:
            raw_doc += line
            if "<DOCNO>" in line:
                url = re.search(r'<DOCNO>(.*?)</DOCNO>', line).group(1).strip()
            elif "</DOC>" in line:
                data = {}
                data['url'] = url
                data['raw_doc'] = raw_doc
                data['inlinks'] = inlinkList[url]
                data['outlinks'] = outlinkList[url]
                crawled_info.append(data)
                raw_doc = ""
                url = ""
                start = False
        elif not start and "<DOC>" in line:
            start = True
            raw_doc += line

def process_data(data):
    raw_doc = data['raw_doc']
    inlinks = list(data['inlinks'])
    outlinks = list(data['outlinks'])

    # parse data
    if re.search(r'<DOCNO>(.*?)</DOCNO>', raw_doc):
        url = re.search(r'<DOCNO>(.*?)</DOCNO>', raw_doc).group(1).strip()
        title = re.search(r'<HEAD>(.*?)</HEAD>', raw_doc)
        if title:
            title = title.group(1).strip()
        else:
            title = 'NA'
        text = re.search(r'<TEXT>(.*?)</TEXT>', raw_doc, flags=re.DOTALL)
        if text:
            text = text.group(1).strip()
        else:
            text = 'NA'

        authors = [AUTHOR_NAME]
        if es.exists(index=INDEX_NAME, id=url):
            # update
            doc = es.get(index=INDEX_NAME, id=url)['_source']['content']

            title = doc.get('title', title)
            text = doc.get('text', text)
            inlinks = list(set(list(doc.get('inlinks', [])) + inlinks))
            outlinks = list(set(list(doc.get('outlinks', [])) + outlinks))
            authors = doc.get('authors', [])
            if AUTHOR_NAME not in authors:
                authors.append(AUTHOR_NAME)

        return {
            '_op_type': 'index',
            '_index': INDEX_NAME,
            '_id': url[:500], # ES ids cant be more than 512 bytes long
            'content': {
                'title': title,
                'text': text,
                'inlinks': inlinks,
                'outlinks': outlinks,
                'authors': authors,
            }
        }
    else:
        print(raw_doc)


index_store = []
with ThreadPoolExecutor(max_workers=10) as executor:
    future_to_data = {executor.submit(process_data, data): data for data in crawled_info}
    for future in tqdm(as_completed(future_to_data), total=len(crawled_info), desc='Processing'):
        result = future.result()
        index_store.append(result)

# merge into ES index
successes = 0
with tqdm(total=len(index_store), desc='Indexing') as pbar:
    for success, info in streaming_bulk(es, index_store):
        if success:
            successes += 1
        pbar.update(1)
    pbar.close()

print(f'{successes} of {len(index_store)} documents indexed successfully!')