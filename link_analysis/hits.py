import math
import os
import random
import pickle
from es_client import get_client, INDEX_NAME

DATA_DIR = "data/link_analysis/"

query = "social justice movements"

# Link graph restricted to indexed pages; produced by pagerank.py
with open(DATA_DIR + 'documents_processed.pickle', 'rb') as handle:
    documents_processed = pickle.load(handle)

# Root set: top 1000 documents retrieved for the query
if os.path.exists(DATA_DIR + 'root_set.pickle'):
    with open(DATA_DIR + 'root_set.pickle', 'rb') as handle:
        root_set = pickle.load(handle)
else:
    es = get_client()
    root_set = {}
    res = es.search(
        index=INDEX_NAME,
        q=query,
        size=1000
    )

    for doc in res['hits']['hits']:
        id = doc['_id']
        inlinks = documents_processed[id]['inlinks']
        outlinks = documents_processed[id]['outlinks']
        root_set.update({id: {'inlinks': inlinks, 'outlinks': outlinks}})

    with open(DATA_DIR + 'root_set.pickle', 'wb') as handle:
        pickle.dump(root_set, handle, protocol=pickle.HIGHEST_PROTOCOL)

# Base set: expand the root set with up to d in/out-linked pages per round
if os.path.exists(DATA_DIR + 'base_set.pickle'):
    with open(DATA_DIR + 'base_set.pickle', 'rb') as handle:
        base_set = pickle.load(handle)
else:
    base_set = {}
    base_set.update(root_set)

    d = 200

    while len(base_set) < 10000:
        outlinks = set([])
        inlinks = set([])
        for page in base_set:
            for outlink in base_set[page]['outlinks']:
                outlinks.add(outlink)
            for inlink in base_set[page]['inlinks']:
                inlinks.add(inlink)

        if len(outlinks) <= d:
            for p in outlinks:
                base_set[p] = documents_processed[p]
        else:
            for p in random.sample(list(outlinks), d):
                base_set[p] = documents_processed[p]

        if len(inlinks) <= d:
            for p in inlinks:
                base_set[p] = documents_processed[p]
        else:
            for p in random.sample(list(inlinks), d):
                base_set[p] = documents_processed[p]

    print(len(base_set))

    with open(DATA_DIR + 'base_set.pickle', 'wb') as handle:
        pickle.dump(base_set, handle, protocol=pickle.HIGHEST_PROTOCOL)

def H(x):
    sum = 0
    for p in x:
        sum += x[p] * math.log(x[p] + 3, 2)
    return -sum

h = {}
a = {}

for p in base_set:
    h[p] = 1
    a[p] = 1

count = 0
prev_a = 0
prev_h = 0

while True:
    if count > 4:
        break
    norm = 0
    for p in base_set:
        a[p] = 0
        for q in base_set[p]['inlinks']:
            if q in base_set:
                a[p] += h[q]
        norm += pow(a[p], 2)
    norm = math.sqrt(norm)
    for p in base_set:
        a[p] = a[p] / norm

    norm = 0
    for p in base_set:
        h[p] = 0
        for q in base_set[p]['outlinks']:
            if q in base_set:
                h[p] += a[q]
        norm += pow(h[p], 2)
    norm = math.sqrt(norm)
    for p in base_set:
        h[p] = h[p] / norm

    current_a = pow(2, H(a))
    current_h = pow(2, H(h))
    print(current_a)
    print(current_h)
    if abs(current_h - prev_h) < 0.00000001 and abs(current_a - prev_a) < 0.00000001:
        count += 1
    else:
        count = 0
    prev_h = current_h
    prev_a = current_a

sorted_h = [(k, v) for k, v in sorted(h.items(), key=lambda item: item[1], reverse=True)]
sorted_a = [(k, v) for k, v in sorted(a.items(), key=lambda item: item[1], reverse=True)]

hub = ""
rank = 1
for url in sorted_h:
    if rank > 500:
        break
    hub += url[0] + "\t" + str(url[1]) + "\n"
    rank += 1

with open('results/link_analysis/hits_hubs_top500.txt', 'w') as f:
    f.write(hub)

auth = ""
rank = 1
for url in sorted_a:
    if rank > 500:
        break
    auth += url[0] + "\t" + str(url[1]) + "\n"
    rank += 1

with open('results/link_analysis/hits_authorities_top500.txt', 'w') as f:
    f.write(auth)
