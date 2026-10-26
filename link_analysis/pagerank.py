import argparse
import math
import os
import pickle
from es_client import get_client, INDEX_NAME

DATA_DIR = "data/link_analysis/"
os.makedirs(DATA_DIR, exist_ok=True)


def scroll_body(scroll_id):
    body = {
        "scroll_id": scroll_id,
        "scroll": "3m"
    }
    return body


def load_crawl_graph():
    # Pull the link graph of every document in the merged team index
    es = get_client()
    documents = {}
    res = es.search(
        index=INDEX_NAME,
        query={"match_all": {}},
        size=500,
        scroll="3m",
        request_timeout=60
    )

    while res['hits']['hits']:
        for doc in res['hits']['hits']:
            id = doc['_id']
            doc = doc["_source"]["content"]
            inlinks = doc.get('inlinks')
            outlinks = doc.get('outlinks')
            documents.update({id: {'inlinks': inlinks, 'outlinks': outlinks}})
        res = es.scroll(body=scroll_body(res['_scroll_id']))

    with open(DATA_DIR + 'documents.pickle', 'wb') as handle:
        pickle.dump(documents, handle, protocol=pickle.HIGHEST_PROTOCOL)

    # Keep only links between pages that are actually in the index
    documents_processed = {}
    for id in documents:
        doc = documents[id]
        inlinks = [x for x in doc['inlinks'] if x in documents]
        outlinks = [x for x in doc['outlinks'] if x in documents]
        documents_processed.update({id: {'inlinks': inlinks, 'outlinks': outlinks}})

    with open(DATA_DIR + 'documents_processed.pickle', 'wb') as handle:
        pickle.dump(documents_processed, handle, protocol=pickle.HIGHEST_PROTOCOL)

    return documents_processed


def load_wt2g_graph(path):
    # Each line: <page> <inlink> <inlink> ... ; outlinks are derived from inlinks
    inlinks = {}
    outlinks = {}
    with open(path, "r") as f:
        lines = f.readlines()
        for line in lines:
            links = line.split(" ")
            id = links.pop(0).strip()
            inlinks[id] = inlinks.get(id, [])
            for link in links:
                link = link.strip()
                if link != "" and link not in inlinks[id]:
                    inlinks[id] += [link]
                    outlinks[link] = outlinks.get(link, []) + [id]

    documents_processed = {}
    for link in inlinks:
        documents_processed[link] = {'inlinks': inlinks.get(link, []), 'outlinks': outlinks.get(link, [])}
    return documents_processed


def H(x):
    sum = 0
    for p in x:
        sum += x[p] * math.log(x[p], 2)
    return -sum


def pagerank(documents_processed, d=0.85):
    PR = {}
    S = {}

    # Sink pages (no outlinks) redistribute their rank to every page
    for p in documents_processed:
        if len(documents_processed[p]['outlinks']) == 0:
            S[p] = documents_processed[p]

    for p in documents_processed:
        PR[p] = 1 / len(documents_processed)

    count = 0
    prev = 0

    # Iterate until perplexity stops changing for several rounds
    while True:
        if count > 4:
            break
        sinkPR = 0
        newPR = {}
        for p in S:
            sinkPR += PR[p]
        for p in documents_processed:
            newPR[p] = (1 - d) / len(documents_processed)
            newPR[p] += d * sinkPR / len(documents_processed)
            for q in documents_processed[p]['inlinks']:
                if len(documents_processed[q]['outlinks']) != 0:
                    newPR[p] += d * PR[q] / len(documents_processed[q]['outlinks'])
        for p in newPR:
            PR[p] = newPR[p]
        current = pow(2, H(PR))
        print(current)
        if current == prev:
            count += 1
        prev = current

    return PR


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Compute PageRank over the crawl graph or the WT2G graph.")
    parser.add_argument("--wt2g", metavar="INLINKS_FILE", help="path to wt2g_inlinks.txt; omit to use the crawl index")
    parser.add_argument("--out", help="output file for the top 500 pages")
    args = parser.parse_args()

    if args.wt2g:
        documents_processed = load_wt2g_graph(args.wt2g)
        out = args.out or "results/link_analysis/pagerank_wt2g_top500.txt"
    else:
        documents_processed = load_crawl_graph()
        out = args.out or "results/link_analysis/pagerank_crawl_top500.txt"

    PR = pagerank(documents_processed)

    ranked = sorted(PR.items(), key=lambda item: item[1], reverse=True)

    result = ""
    rank = 1
    for url in ranked:
        if rank > 500:
            break
        result += str(rank) + ". " + url[0] + ": inlinks - " + str(len(documents_processed[url[0]]['inlinks'])) + ", outlinks - " + str(len(documents_processed[url[0]]['outlinks'])) + ", score: " + str(url[1]) + "\n"
        rank += 1

    with open(out, 'w') as f:
        f.write(result)
